"use client";

import Link from "next/link";
import { Bot, MessageSquareText, ClipboardCheck, GitMerge, FileBarChart, Lightbulb, ChevronRight } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api";
import { Card, Badge, Skeleton } from "@/components/ui";
import { capitalize } from "@/lib/utils/utils";
import { formatTimeAgo } from "@/lib/utils/format";
import type { AgentTemplate, AgentKey } from "@/types";

const AGENT_META: Record<AgentKey, { label: string; icon: typeof Bot; description: string }> = {
  interviewer: { label: "Interviewer", icon: MessageSquareText, description: "Asks questions, manages pacing, adapts tone. Chooses topics from the candidate's own knowledge." },
  evaluator: { label: "Evaluator", icon: ClipboardCheck, description: "Scores every answer against the rubric." },
  router: { label: "Router", icon: GitMerge, description: "Decides follow-up, next question, or end — rule-based." },
  feedback: { label: "Feedback", icon: FileBarChart, description: "Generates the post-interview coaching report." },
  coach: { label: "Coach", icon: Lightbulb, description: "Live hints during practice mode." },
};

const AGENT_KEYS: AgentKey[] = ["interviewer", "evaluator", "router", "feedback", "coach"];

export default function AdminAgentsPage() {
  const { data: agents, isLoading } = useApiQuery<AgentTemplate[]>({ url: "/admin/agents/" });

  const byKey = (key: AgentKey) => (agents ?? []).filter((a) => a.key === key);

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">AI Studio — Agents</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Each card is a sub-agent. Clone before editing — published versions are immutable.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {AGENT_KEYS.map((key) => {
          const meta = AGENT_META[key];
          const versions = byKey(key);
          const active = versions.find((v) => v.status === "active");

          return (
            <Card key={key} className="p-5 flex flex-col">
              <div className="flex items-start gap-3 mb-3">
                <div className="p-2.5 rounded-lg bg-primary/10 flex-shrink-0">
                  <meta.icon className="w-4.5 h-4.5 text-primary" />
                </div>
                <div className="min-w-0">
                  <h3 className="font-display font-semibold text-foreground">{meta.label}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{meta.description}</p>
                </div>
              </div>

              {isLoading ? (
                <Skeleton className="h-16 w-full mt-2" />
              ) : active ? (
                <div className="mt-2 space-y-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="success">v{active.version} active</Badge>
                    <span className="text-xs text-muted-foreground">{formatTimeAgo(active.publishedAt)}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {active.modelProvider === "rule_engine" ? "Rule engine" : `${active.modelName} · temp ${active.temperature}`}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground mt-2">No active version configured yet.</p>
              )}

              <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{versions.length} version{versions.length === 1 ? "" : "s"}</span>
                {active ? (
                  <Link href={`/admin/agents/${active.id}`} className="text-xs text-primary hover:text-primary/80 font-medium flex items-center gap-1 transition-colors">
                    Manage <ChevronRight className="w-3 h-3" />
                  </Link>
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
