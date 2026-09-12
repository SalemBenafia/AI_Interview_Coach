"use client";

import { useEffect } from "react";
import { Wifi, WifiOff, RotateCcw } from "lucide-react";
import { useInterviewStore } from "@/store/use-interview-store";
import { cn, capitalize, difficultyVariant } from "@/lib/utils/utils";
import { Badge } from "@/components/ui";
import type { InterviewSession } from "@/types";

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

const CONNECTION_CONFIG: Record<string, { icon: typeof Wifi; label: string; classes: string }> = {
  idle: { icon: Wifi, label: "Preparing…", classes: "text-muted-foreground" },
  connecting: { icon: RotateCcw, label: "Connecting…", classes: "text-warning" },
  connected: { icon: Wifi, label: "Connected", classes: "text-success" },
  reconnecting: { icon: RotateCcw, label: "Reconnecting…", classes: "text-warning" },
  disconnected: { icon: WifiOff, label: "Disconnected", classes: "text-error" },
};

export function InterviewTopBar({ session }: { session: InterviewSession | undefined }) {
  const connectionState = useInterviewStore((s) => s.connectionState);
  const elapsedSeconds = useInterviewStore((s) => s.elapsedSeconds);
  const tickElapsed = useInterviewStore((s) => s.tickElapsed);

  useEffect(() => {
    const interval = setInterval(tickElapsed, 1000);
    return () => clearInterval(interval);
  }, [tickElapsed]);

  const connConfig = CONNECTION_CONFIG[connectionState];

  return (
    <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/5 bg-card/40 backdrop-blur-md">
      <div className="flex items-center gap-3 min-w-0">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            {session?.targetRoleTitle ?? "General Interview"}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-muted-foreground capitalize">
              {session?.mode.replace("_", " ")}
            </span>
            {session?.difficulty && (
              <Badge variant={difficultyVariant[session.difficulty] === "warning" ? "warning" : "default"}>
                {capitalize(session.difficulty)}
              </Badge>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <span className="font-mono-coach text-sm text-muted-foreground tabular-nums">
          {formatElapsed(elapsedSeconds)}
        </span>
        <div className={cn("flex items-center gap-1.5 text-xs font-medium", connConfig.classes)}>
          <connConfig.icon className={cn("w-3.5 h-3.5", connectionState === "reconnecting" && "animate-spin")} />
          {connConfig.label}
        </div>
      </div>
    </div>
  );
}
