"use client";

import { Lightbulb, X } from "lucide-react";
import { useInterviewStore } from "@/store/use-interview-store";

export function HintBanner() {
  const hint = useInterviewStore((s) => s.currentHint);
  const setHint = useInterviewStore((s) => s.setHint);

  if (!hint) return null;

  return (
    <div className="flex items-center gap-3 px-4 py-3 mx-5 mb-3 rounded-lg bg-accent/10 border border-accent/20 animate-fade-in">
      <Lightbulb className="w-4 h-4 text-accent flex-shrink-0" />
      <p className="text-sm text-foreground flex-1">{hint}</p>
      <button
        type="button"
        onClick={() => setHint(null)}
        className="text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
        aria-label="Dismiss hint"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
