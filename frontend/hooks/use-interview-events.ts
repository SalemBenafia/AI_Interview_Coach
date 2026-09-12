"use client";

/**
 * hooks/use-interview-events.ts
 * ================================
 * Subscribes to the live transcript/turn-event stream for one interview
 * session. Browsers send the HttpOnly access-token cookie automatically on
 * same-site WebSocket handshakes, so no token handling is needed here.
 */
import { useEffect, useRef } from "react";
import { useInterviewStore } from "@/store/use-interview-store";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
const RECONNECT_DELAY_MS = 2500;
const MAX_RECONNECT_ATTEMPTS = 5;

interface AiTurnEvent {
  type: "ai_turn" | "candidate_turn" | "connected" | "heartbeat";
  session_id?: string;
  turn_number?: number;
  text?: string;
  hint?: string | null;
  should_end?: boolean;
}

export function useInterviewEvents(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalClose = useRef(false);

  const addCaption = useInterviewStore((s) => s.addCaption);
  const setHint = useInterviewStore((s) => s.setHint);
  const setShouldEnd = useInterviewStore((s) => s.setShouldEnd);
  const setAgentVoiceState = useInterviewStore((s) => s.setAgentVoiceState);

  useEffect(() => {
    if (!sessionId) return;
    intentionalClose.current = false;

    function connect() {
      const ws = new WebSocket(`${WS_URL}/ws/interview/${sessionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectCount.current = 0;
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data as string) as AiTurnEvent;
          if (msg.type === "candidate_turn" && msg.text) {
            addCaption({
              speaker: "candidate",
              text: msg.text,
              turnNumber: msg.turn_number ?? 0,
              timestamp: Date.now(),
            });
          } else if (msg.type === "ai_turn" && msg.text) {
            addCaption({
              speaker: "ai",
              text: msg.text,
              turnNumber: msg.turn_number ?? 0,
              timestamp: Date.now(),
            });
            setHint(msg.hint ?? null);
            setAgentVoiceState("speaking");
            if (msg.should_end) setShouldEnd(true);
          }
        } catch {
          // Ignore malformed messages.
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (!intentionalClose.current && reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectCount.current += 1;
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };
    }

    connect();

    return () => {
      intentionalClose.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sessionId, addCaption, setHint, setShouldEnd, setAgentVoiceState]);
}
