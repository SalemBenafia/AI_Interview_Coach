"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Mic, ShieldCheck, Loader2, PanelRightOpen, PanelRightClose } from "lucide-react";
import { useLiveKitRoom } from "@/hooks/use-livekit-room";
import { useInterviewEvents } from "@/hooks/use-interview-events";
import { useEndOnUnload } from "@/hooks/use-end-on-unload";
import { useInterviewStore } from "@/store/use-interview-store";
import { useApiQuery } from "@/hooks/use-api";
import { interviewService } from "@/lib/api/services";
import { InterviewTopBar } from "@/components/interview/InterviewTopBar";
import { VoiceVisualizer } from "@/components/interview/VoiceVisualizer";
import { TranscriptPanel } from "@/components/interview/TranscriptPanel";
import { InterviewControls } from "@/components/interview/InterviewControls";
import { HintBanner } from "@/components/interview/HintBanner";
import { useToast } from "@/store/use-ui-store";
import type { InterviewSession } from "@/types";
import type { SuccessResponse } from "@/hooks/use-api";

export default function InterviewRoomPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  const router = useRouter();
  const { toast } = useToast();

  const [joined, setJoined] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [ending, setEnding] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(true);

  const shouldEnd = useInterviewStore((s) => s.shouldEnd);
  const micMuted = useInterviewStore((s) => s.micMuted);
  const resetInterviewStore = useInterviewStore((s) => s.reset);

  const { data: session } = useApiQuery<InterviewSession>({
    url: `/interviews/sessions/${sessionId}/`,
    enabled: !!sessionId,
  });

  const { audioElRef } = useLiveKitRoom(joined ? sessionId : null);
  useInterviewEvents(joined ? sessionId : null);
  useEndOnUnload(sessionId, joined && !shouldEnd);

  useEffect(() => {
    return () => resetInterviewStore();
  }, [resetInterviewStore]);

  useEffect(() => {
    if (shouldEnd) {
      const timer = setTimeout(() => {
        router.push(`/candidate/interview/${sessionId}/report`);
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [shouldEnd, sessionId, router]);

  const handlePause = async () => {
    try {
      await interviewService.pauseSession(sessionId);
      setIsPaused(true);
    } catch {
      toast.error("Couldn't pause the interview");
    }
  };

  const handleResume = async () => {
    try {
      await interviewService.resumeSession(sessionId);
      setIsPaused(false);
    } catch {
      toast.error("Couldn't resume the interview");
    }
  };

  const handleEnd = async () => {
    setEnding(true);
    try {
      await interviewService.endSession(sessionId);
      router.push(`/candidate/interview/${sessionId}/report`);
    } catch {
      toast.error("Couldn't end the interview cleanly — your progress is still saved.");
      setEnding(false);
    }
  };

  if (!joined) {
    return <PreJoinScreen onJoin={() => setJoined(true)} session={session} />;
  }

  if (shouldEnd) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-background">
        <Loader2 className="w-6 h-6 text-primary animate-spin" />
        <p className="text-sm text-muted-foreground">Wrapping up and preparing your feedback report…</p>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background circuit-grid">
      {/* Plays the AI's synthesized voice from the LiveKit room.
          Use sr-only (not hidden/display:none) — some browsers suppress
          the audio context for elements removed from the render tree. */}
      <audio ref={audioElRef} autoPlay className="sr-only" />

      <InterviewTopBar session={session} />

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col items-center justify-center relative px-6">
          <button
            type="button"
            onClick={() => setTranscriptOpen((p) => !p)}
            className="absolute top-4 right-4 hidden lg:flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2.5 py-1.5 rounded-md hover:bg-white/5 transition-colors"
          >
            {transcriptOpen ? <PanelRightClose className="w-3.5 h-3.5" /> : <PanelRightOpen className="w-3.5 h-3.5" />}
            Transcript
          </button>

          {isPaused && (
            <div className="absolute top-4 left-4 px-3 py-1.5 rounded-full bg-warning/15 text-warning text-xs font-medium border border-warning/25">
              Paused
            </div>
          )}

          <VoiceVisualizer micMuted={micMuted} />
        </div>

        {transcriptOpen && (
          <aside className="hidden lg:flex w-80 flex-col border-l border-white/5 bg-card/30 backdrop-blur-sm p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 px-1">
              Live transcript
            </h3>
            <TranscriptPanel />
          </aside>
        )}
      </div>

      <HintBanner />
      <InterviewControls onEnd={handleEnd} onPause={handlePause} onResume={handleResume} isPaused={isPaused} ending={ending} />
    </div>
  );
}

// ─── Pre-join screen ──────────────────────────────────────────────────────────

function PreJoinScreen({
  onJoin,
  session,
}: {
  onJoin: () => void;
  session: InterviewSession | undefined;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background circuit-grid px-6">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="inline-flex p-4 rounded-full bg-primary/10 glow-border">
          <Mic className="w-7 h-7 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Ready to begin?</h1>
          <p className="text-sm text-muted-foreground mt-2">
            {session?.targetRoleTitle ?? "Your interview"} · {session?.mode.replace("_", " ")} · {session?.difficulty}
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 text-left space-y-3">
          <div className="flex items-start gap-3">
            <ShieldCheck className="w-4 h-4 text-accent mt-0.5 flex-shrink-0" />
            <p className="text-sm text-muted-foreground">
              We'll ask for microphone access. The AI interviewer will greet you and ask its first
              question as soon as you join — speak naturally, just like a real call.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onJoin}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary text-primary-foreground font-semibold py-4 hover:shadow-neon hover:brightness-110 transition-all text-base"
        >
          <Mic className="w-5 h-5" />
          Join the interview
        </button>
      </div>
    </div>
  );
}
