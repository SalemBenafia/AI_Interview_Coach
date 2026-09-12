"use client";

import { useState } from "react";
import { Mic, MicOff, PhoneOff, Pause, Play, Loader2 } from "lucide-react";
import { useInterviewStore } from "@/store/use-interview-store";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { cn } from "@/lib/utils/utils";

interface InterviewControlsProps {
  onEnd: () => Promise<void>;
  onPause: () => Promise<void>;
  onResume: () => Promise<void>;
  isPaused: boolean;
  ending: boolean;
}

export function InterviewControls({ onEnd, onPause, onResume, isPaused, ending }: InterviewControlsProps) {
  const micMuted = useInterviewStore((s) => s.micMuted);
  const toggleMic = useInterviewStore((s) => s.toggleMic);
  const [confirmEndOpen, setConfirmEndOpen] = useState(false);

  return (
    <>
      <div className="flex items-center justify-center gap-3 px-5 py-5 border-t border-white/5 bg-card/40 backdrop-blur-md">
        <button
          type="button"
          onClick={toggleMic}
          className={cn(
            "flex items-center justify-center w-12 h-12 rounded-full transition-all",
            micMuted
              ? "bg-error/15 text-error hover:bg-error/25"
              : "bg-white/5 text-foreground hover:bg-white/10"
          )}
          aria-label={micMuted ? "Unmute microphone" : "Mute microphone"}
        >
          {micMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>

        <button
          type="button"
          onClick={isPaused ? onResume : onPause}
          className="flex items-center justify-center w-12 h-12 rounded-full bg-white/5 text-foreground hover:bg-white/10 transition-all"
          aria-label={isPaused ? "Resume interview" : "Pause interview"}
        >
          {isPaused ? <Play className="w-5 h-5" /> : <Pause className="w-5 h-5" />}
        </button>

        <button
          type="button"
          onClick={() => setConfirmEndOpen(true)}
          disabled={ending}
          className="flex items-center justify-center w-14 h-12 rounded-full bg-error text-white hover:bg-error/90 disabled:opacity-60 transition-all"
          aria-label="End interview"
        >
          {ending ? <Loader2 className="w-5 h-5 animate-spin" /> : <PhoneOff className="w-5 h-5" />}
        </button>
      </div>

      <ConfirmDialog
        open={confirmEndOpen}
        onClose={() => setConfirmEndOpen(false)}
        onConfirm={() => {
          setConfirmEndOpen(false);
          onEnd();
        }}
        title="End this interview?"
        description="You'll still get a feedback report based on what you've covered so far, but you won't be able to continue this session."
        confirmLabel="End interview"
        destructive
      />
    </>
  );
}
