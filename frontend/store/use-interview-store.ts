/**
 * store/use-interview-store.ts
 * ===============================
 * Live interview session state, populated by the WebSocket event stream
 * (hooks/use-interview-events.ts) and the LiveKit room hook
 * (hooks/use-livekit-room.ts). This is the single source of truth the
 * live interview room UI (app/interview/[sessionId]/page.tsx) renders from.
 */
import { create } from "zustand";
import { devtools } from "zustand/middleware";

export interface CaptionEntry {
  id: string;
  speaker: "ai" | "candidate";
  text: string;
  turnNumber: number;
  timestamp: number;
}

export type ConnectionState = "idle" | "connecting" | "connected" | "reconnecting" | "disconnected";
export type AgentVoiceState = "idle" | "listening" | "thinking" | "speaking";

interface InterviewState {
  connectionState: ConnectionState;
  agentVoiceState: AgentVoiceState;
  micMuted: boolean;
  captions: CaptionEntry[];
  currentHint: string | null;
  shouldEnd: boolean;
  elapsedSeconds: number;
  audioLevel: number; // 0-1, candidate mic level for the voice orb

  setConnectionState: (state: ConnectionState) => void;
  setAgentVoiceState: (state: AgentVoiceState) => void;
  toggleMic: () => void;
  setMicMuted: (muted: boolean) => void;
  addCaption: (entry: Omit<CaptionEntry, "id">) => void;
  setHint: (hint: string | null) => void;
  setShouldEnd: (value: boolean) => void;
  tickElapsed: () => void;
  resetElapsed: () => void;
  setAudioLevel: (level: number) => void;
  reset: () => void;
}

export const useInterviewStore = create<InterviewState>()(
  devtools(
    (set) => ({
      connectionState: "idle",
      agentVoiceState: "idle",
      micMuted: false,
      captions: [],
      currentHint: null,
      shouldEnd: false,
      elapsedSeconds: 0,
      audioLevel: 0,

      setConnectionState: (connectionState) =>
        set({ connectionState }, false, "interview/setConnectionState"),
      setAgentVoiceState: (agentVoiceState) =>
        set({ agentVoiceState }, false, "interview/setAgentVoiceState"),
      toggleMic: () => set((s) => ({ micMuted: !s.micMuted }), false, "interview/toggleMic"),
      setMicMuted: (micMuted) => set({ micMuted }, false, "interview/setMicMuted"),
      addCaption: (entry) =>
        set(
          (s) => ({
            captions: [...s.captions, { ...entry, id: `${entry.turnNumber}-${entry.speaker}-${Date.now()}` }],
          }),
          false,
          "interview/addCaption"
        ),
      setHint: (currentHint) => set({ currentHint }, false, "interview/setHint"),
      setShouldEnd: (shouldEnd) => set({ shouldEnd }, false, "interview/setShouldEnd"),
      tickElapsed: () => set((s) => ({ elapsedSeconds: s.elapsedSeconds + 1 }), false, "interview/tick"),
      resetElapsed: () => set({ elapsedSeconds: 0 }, false, "interview/resetElapsed"),
      setAudioLevel: (audioLevel) => set({ audioLevel }, false, "interview/setAudioLevel"),
      reset: () =>
        set(
          {
            connectionState: "idle",
            agentVoiceState: "idle",
            micMuted: false,
            captions: [],
            currentHint: null,
            shouldEnd: false,
            elapsedSeconds: 0,
            audioLevel: 0,
          },
          false,
          "interview/reset"
        ),
    }),
    { name: "InterviewCoach/Interview" }
  )
);
