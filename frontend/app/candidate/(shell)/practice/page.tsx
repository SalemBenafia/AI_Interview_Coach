"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Briefcase, Mic, Sparkles,
  MessageSquareText, Brain, ShieldCheck, Loader2, Lightbulb, Plus,
} from "lucide-react";
import { useApiQuery } from "@/hooks/use-api";
import { interviewService } from "@/lib/api/services";
import { Toggle } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";
import { cn } from "@/lib/utils/utils";
import type { CandidateTargetRole, ModeOption, DifficultyOption } from "@/types";

const MODE_ICONS: Record<string, typeof MessageSquareText> = {
  behavioral: MessageSquareText,
  technical: Brain,
  mixed: Sparkles,
  mock_hr_screening: ShieldCheck,
};

const DIFFICULTY_COLOR: Record<string, string> = {
  junior: "border-difficulty-junior/30 text-difficulty-junior",
  mid: "border-difficulty-mid/30 text-difficulty-mid",
  senior: "border-difficulty-senior/30 text-difficulty-senior",
};

export default function PracticePage() {
  const router = useRouter();
  const { toast } = useToast();

  const { data: targetRoles } = useApiQuery<CandidateTargetRole[]>({ url: "/target-roles/" });
  const { data: modes } = useApiQuery<ModeOption[]>({ url: "/catalog/modes/" });
  const { data: difficulties } = useApiQuery<DifficultyOption[]>({ url: "/catalog/difficulty-levels/" });

  const readyTargetRoles = (targetRoles ?? []).filter((r) => r.status === "ready");

  const [targetRoleId, setTargetRoleId] = useState<string | null>(null);
  const [mode, setMode] = useState<string>("mixed");
  const [difficulty, setDifficulty] = useState<string>("mid");
  const [liveCoaching, setLiveCoaching] = useState(false);
  const [recordingConsent, setRecordingConsent] = useState(true);
  const [creating, setCreating] = useState(false);

  const handleStart = async () => {
    setCreating(true);
    try {
      const result = await interviewService.createSession({
        target_role_id: targetRoleId ?? undefined,
        mode,
        difficulty,
        live_coaching_enabled: liveCoaching,
        recording_consent: recordingConsent,
      });

      const sessionId = result?.sessionId;

      if (!sessionId) {
        throw new Error("No session ID received from server");
      }

      router.push(`/candidate/interview/${sessionId}`);
    } catch (err: any) {
      console.error("Create session error:", err);
      toast.error("Couldn't start the interview", "Please check your connection and try again.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Set up your interview</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Pick one of your target roles, a mode, and a difficulty — the AI grounds questions in your own
          background for that role.
        </p>
      </div>

      {/* Role */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Target role</h2>
          <Link
            href="/candidate/target-roles"
            className="text-xs text-primary hover:underline inline-flex items-center gap-1"
          >
            <Plus className="w-3 h-3" />
            Manage target roles
          </Link>
        </div>

        {readyTargetRoles.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-6 text-center">
            <Briefcase className="w-5 h-5 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-foreground font-medium">No ready target roles yet</p>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
              Create a target role and add your background so the AI can ground questions in it — or start a
              general practice session below.
            </p>
            <Link
              href="/candidate/target-roles"
              className="inline-flex items-center gap-1.5 mt-3 text-xs font-medium text-primary hover:underline"
            >
              <Plus className="w-3.5 h-3.5" />
              Create a target role
            </Link>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <button
              type="button"
              onClick={() => setTargetRoleId(null)}
              className={cn(
                "flex items-center gap-3 rounded-xl border p-4 text-left transition-all",
                targetRoleId === null ? "border-primary bg-primary/5 shadow-neon-sm" : "border-border hover:border-white/20"
              )}
            >
              <div className="p-2 rounded-lg bg-muted">
                <Sparkles className="w-4 h-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">General</p>
                <p className="text-xs text-muted-foreground">No specific role focus</p>
              </div>
            </button>

            {readyTargetRoles.map((role) => {
              const selected = targetRoleId === role.id;
              return (
                <button
                  key={role.id}
                  type="button"
                  onClick={() => setTargetRoleId(role.id)}
                  className={cn(
                    "flex items-center gap-3 rounded-xl border p-4 text-left transition-all",
                    selected ? "border-primary bg-primary/5 shadow-neon-sm" : "border-border hover:border-white/20"
                  )}
                >
                  <div className={cn("p-2 rounded-lg", selected ? "bg-primary/15" : "bg-muted")}>
                    <Briefcase className={cn("w-4 h-4", selected ? "text-primary" : "text-muted-foreground")} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{role.title}</p>
                    <p className="text-xs text-muted-foreground truncate">
                      {role.description ?? "Your own background is ready"}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Mode */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Interview mode</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(modes ?? []).map((m) => {
            const Icon = MODE_ICONS[m.value] ?? MessageSquareText;
            const selected = mode === m.value;
            return (
              <button
                key={m.value}
                type="button"
                onClick={() => setMode(m.value)}
                className={cn(
                  "rounded-xl border p-4 text-left transition-all",
                  selected ? "border-primary bg-primary/5 shadow-neon-sm" : "border-border hover:border-white/20"
                )}
              >
                <Icon className={cn("w-4 h-4 mb-2", selected ? "text-primary" : "text-muted-foreground")} />
                <p className="text-sm font-medium text-foreground">{m.label}</p>
                <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{m.description}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Difficulty */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Difficulty</h2>
        <div className="grid sm:grid-cols-3 gap-3">
          {(difficulties ?? []).map((d) => {
            const selected = difficulty === d.value;
            return (
              <button
                key={d.value}
                type="button"
                onClick={() => setDifficulty(d.value)}
                className={cn(
                  "rounded-xl border-2 p-4 text-left transition-all",
                  selected ? DIFFICULTY_COLOR[d.value] ?? "border-primary" : "border-border hover:border-white/20"
                )}
              >
                <p className="text-sm font-semibold text-foreground capitalize">{d.label}</p>
                <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{d.description}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Options */}
      <section className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-start gap-3">
            <Lightbulb className="w-4 h-4 text-accent mt-0.5" />
            <div>
              <p className="text-sm font-medium text-foreground">Live coaching hints</p>
              <p className="text-xs text-muted-foreground">
                The AI drops short structural hints mid-interview. Turn off for full realism.
              </p>
            </div>
          </div>
          <Toggle checked={liveCoaching} onChange={setLiveCoaching} />
        </div>
        <div className="h-px bg-border" />
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Allow recording</p>
            <p className="text-xs text-muted-foreground">Used only to generate your feedback report.</p>
          </div>
          <Toggle checked={recordingConsent} onChange={setRecordingConsent} />
        </div>
      </section>

      <button
        type="button"
        onClick={handleStart}
        disabled={creating}
        className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary text-primary-foreground font-semibold py-4 hover:shadow-neon hover:brightness-110 disabled:opacity-60 transition-all text-base"
      >
        {creating ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <>
            <Mic className="w-5 h-5" />
            Start the interview
          </>
        )}
      </button>
    </div>
  );
}
