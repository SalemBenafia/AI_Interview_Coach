"use client";

/**
 * components/interview/VoiceVisualizer.tsx
 * ============================================
 * The live call's focal point. Reacts to real state:
 *  - "listening": scales with the candidate's actual mic audioLevel
 *    (from LiveKit's localParticipant.audioLevel, polled in
 *    hooks/use-livekit-room.ts)
 *  - "speaking": rhythmic pulse while the AI's synthesized voice plays
 *  - "thinking": a quicker spin while a turn is being processed
 *  - "idle": a slow resting breathe
 */
import { useInterviewStore } from "@/store/use-interview-store";
import { cn } from "@/lib/utils/utils";

const STATE_LABEL: Record<string, string> = {
  idle: "Ready",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
};

export function VoiceVisualizer({ micMuted }: { micMuted: boolean }) {
  const agentVoiceState = useInterviewStore((s) => s.agentVoiceState);
  const audioLevel = useInterviewStore((s) => s.audioLevel);

  const listening = agentVoiceState === "listening" && !micMuted;
  const speaking = agentVoiceState === "speaking";
  const thinking = agentVoiceState === "thinking";

  const ringScale = listening ? 1 + Math.min(audioLevel * 1.8, 0.5) : 1;

  return (
    <div className="relative flex flex-col items-center justify-center gap-6">
      <div className="relative w-56 h-56 flex items-center justify-center">
        {/* Outer ambient rings */}
        <div
          className={cn(
            "absolute inset-0 rounded-full border transition-all duration-150",
            speaking ? "border-accent/30" : "border-primary/20"
          )}
          style={{ transform: `scale(${ringScale * 1.3})`, opacity: listening ? 0.5 : 0.3 }}
        />
        <div
          className={cn(
            "absolute inset-4 rounded-full border transition-all duration-150",
            speaking ? "border-accent/40" : "border-primary/30"
          )}
          style={{ transform: `scale(${ringScale * 1.15})`, opacity: listening ? 0.6 : 0.4 }}
        />

        {/* Core orb */}
        <div
          className={cn(
            "relative w-32 h-32 rounded-full flex items-center justify-center transition-all duration-150",
            speaking && "animate-orb-pulse",
            thinking && "animate-spin",
            micMuted ? "bg-muted" : "bg-gradient-to-br from-primary to-accent"
          )}
          style={{
            transform: !speaking && !thinking ? `scale(${ringScale})` : undefined,
            boxShadow: micMuted
              ? "none"
              : `0 0 ${40 + audioLevel * 60}px hsl(156 100% 50% / ${0.25 + audioLevel * 0.3})`,
          }}
        >
          {thinking ? (
            <div className="grid grid-cols-3 gap-1">
              {Array.from({ length: 9 }).map((_, i) => (
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-primary-foreground/80" />
              ))}
            </div>
          ) : (
            <WaveformBars active={speaking || listening} muted={micMuted} />
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span
          className={cn(
            "w-1.5 h-1.5 rounded-full",
            speaking || listening ? "bg-primary animate-pulse" : "bg-muted-foreground"
          )}
        />
        <span className="text-sm text-muted-foreground font-medium">
          {micMuted && agentVoiceState !== "speaking" ? "Microphone muted" : STATE_LABEL[agentVoiceState]}
        </span>
      </div>
    </div>
  );
}

function WaveformBars({ active, muted }: { active: boolean; muted: boolean }) {
  const heights = [0.4, 0.7, 1, 0.6, 0.45];
  return (
    <div className="flex items-center gap-1 h-8">
      {heights.map((h, i) => (
        <span
          key={i}
          className={cn(
            "w-1 rounded-full bg-primary-foreground",
            active && !muted && "animate-waveform-bar"
          )}
          style={{
            height: `${h * 100}%`,
            animationDelay: `${i * 0.12}s`,
            opacity: muted ? 0.3 : active ? 1 : 0.6,
          }}
        />
      ))}
    </div>
  );
}
