"use client";

import { useCallback, useEffect, useRef } from "react";
import {
  RoomEvent,
  Track,
  createRoom,
  type Room,
  type RemoteTrack,
  type RemoteTrackPublication,
} from "@/lib/webrtc/livekit";
import { livekitService } from "@/lib/api/services";
import { useInterviewStore } from "@/store/use-interview-store";

export function useLiveKitRoom(sessionId: string | null) {
  const roomRef = useRef<Room | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const rafRef = useRef<number | null>(null);

  const setConnectionState = useInterviewStore((s) => s.setConnectionState);
  const setAgentVoiceState = useInterviewStore((s) => s.setAgentVoiceState);
  const micMuted = useInterviewStore((s) => s.micMuted);

  const pollAudioLevel = useCallback(() => {
    const room = roomRef.current;
    if (room?.localParticipant) {
      useInterviewStore.getState().setAudioLevel(room.localParticipant.audioLevel ?? 0);
    }
    rafRef.current = requestAnimationFrame(pollAudioLevel);
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;

    async function connect() {
      setConnectionState("connecting");
      try {
        const { livekitUrl, token } = await livekitService.getJoinToken(sessionId as string);
        if (cancelled) return;

        const room = createRoom();
        roomRef.current = room;

        room.on(RoomEvent.Connected, () => setConnectionState("connected"));
        room.on(RoomEvent.Reconnecting, () => setConnectionState("reconnecting"));
        room.on(RoomEvent.Reconnected, () => setConnectionState("connected"));
        room.on(RoomEvent.Disconnected, () => setConnectionState("disconnected"));

        room.on(
          RoomEvent.TrackSubscribed,
          (track: RemoteTrack, _pub: RemoteTrackPublication) => {
            if (track.kind === Track.Kind.Audio && audioElRef.current) {
              track.attach(audioElRef.current);
              // Explicit play() after attach: Firefox suspends the audio
              // context when srcObject is set asynchronously (past the
              // user-gesture window). Calling play() here re-triggers the
              // browser's permission check in the right context.
              audioElRef.current.play().catch(() => {
                // Audio context still suspended — unlock it via startAudio().
                room.startAudio();
              });
              setAgentVoiceState("speaking");
            }
          }
        );

        room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
          if (track.kind === Track.Kind.Audio) {
            track.detach();
            setAgentVoiceState("idle");
          }
        });

        room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
          const aiSpeaking = speakers.some((p) => !p.isLocal);
          const candidateSpeaking = speakers.some((p) => p.isLocal);
          if (aiSpeaking) {
            setAgentVoiceState("speaking");
          } else if (candidateSpeaking) {
            setAgentVoiceState("listening");
          } else {
            setAgentVoiceState("thinking");
          }
        });

        await room.connect(livekitUrl, token, { autoSubscribe: true });
        // Unlock the browser audio context immediately after connect, while
        // we are still inside the user-gesture call chain (the "Join" click).
        // Without this, Firefox/Chrome suspend the audio context when
        // track.attach() sets srcObject asynchronously, so the audio element
        // receives data but never plays — the user hears nothing.
        await room.startAudio();
        await room.localParticipant.setMicrophoneEnabled(!micMuted);

        rafRef.current = requestAnimationFrame(pollAudioLevel);
      } catch (error) {
        if (!cancelled) {
          setConnectionState("disconnected");
          console.error("Failed to connect to LiveKit room:", error);
        }
      }
    }

    connect();

    return () => {
      cancelled = true;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      roomRef.current?.disconnect?.();
      roomRef.current = null;
    };
  }, [sessionId]);

  useEffect(() => {
    roomRef.current?.localParticipant.setMicrophoneEnabled(!micMuted);
  }, [micMuted]);

  return { audioElRef, room: roomRef };
}
