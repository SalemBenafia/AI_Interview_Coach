"use client";

import { useEffect, useRef } from "react";
import { Bot, User } from "lucide-react";
import { useInterviewStore } from "@/store/use-interview-store";
import { cn } from "@/lib/utils/utils";

export function TranscriptPanel() {
  const captions = useInterviewStore((s) => s.captions);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [captions.length]);

  if (captions.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
        Your live transcript will appear here once the interview starts.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto scrollbar-thin space-y-3 px-1">
      {captions.map((entry) => (
        <div
          key={entry.id}
          className={cn("flex gap-2.5 max-w-[85%]", entry.speaker === "candidate" && "ml-auto flex-row-reverse")}
        >
          <div
            className={cn(
              "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0",
              entry.speaker === "ai" ? "bg-primary/15" : "bg-accent/15"
            )}
          >
            {entry.speaker === "ai" ? (
              <Bot className="w-3.5 h-3.5 text-primary" />
            ) : (
              <User className="w-3.5 h-3.5 text-accent" />
            )}
          </div>
          <div
            className={cn(
              "rounded-xl px-3.5 py-2.5 text-sm leading-relaxed",
              entry.speaker === "ai"
                ? "bg-card border border-white/8 text-foreground"
                : "bg-accent/10 text-foreground"
            )}
          >
            {entry.text}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
