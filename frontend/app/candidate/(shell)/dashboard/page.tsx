"use client";

import Link from "next/link";
import {
  Mic, ArrowRight, TrendingUp, Target, Sparkles, Clock, ChevronRight,
} from "lucide-react";
import { useApiQuery, useApiPaginated } from "@/hooks/use-api";
import { interviewService } from "@/lib/api/services";
import { Card, CardContent, Badge, Skeleton, ScoreRing } from "@/components/ui";
import { capitalize, hasSessionReport, sessionStatusVariant } from "@/lib/utils/utils";
import { formatTimeAgo } from "@/lib/utils/format";
import type { CandidateStats, InterviewSession } from "@/types";
import { useAuth } from "@/hooks/use-auth";

export default function DashboardPage() {
  const { user } = useAuth();

  const { data: stats, isLoading: statsLoading } = useApiQuery<CandidateStats>({
    url: "/interviews/me/stats/",
  });

  // useApiQuery unwraps one level (response.data.data) -- for a paginated
  // endpoint that field IS the array, and `meta` sits alongside it, not
  // nested inside it. useApiPaginated returns the whole envelope
  // ({ data, meta }) instead, which is what's actually needed here.
  const { data: sessionsRes, isLoading: sessionsLoading } = useApiPaginated<InterviewSession>({
    url: "/interviews/sessions/",
    params: { page: 1, limit: 5 },
  });

  const recentSessions = sessionsRes?.data ?? [];
  const latestScore = stats?.scoreTrend?.[stats.scoreTrend.length - 1]?.overallScore ?? null;
  const previousScore = stats?.scoreTrend?.[stats.scoreTrend.length - 2]?.overallScore ?? null;
  const trendDelta = latestScore != null && previousScore != null ? Math.round(latestScore - previousScore) : null;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Greeting + CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">
            Welcome back{user?.firstName ? `, ${user.firstName}` : ""}
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {stats?.totalCompletedInterviews
              ? `${stats.totalCompletedInterviews} interviews completed so far.`
              : "Run your first practice interview to see your stats here."}
          </p>
        </div>
        <Link
          href="/candidate/practice"
          className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold px-5 py-2.5 hover:shadow-neon-sm hover:brightness-110 transition-all flex-shrink-0"
        >
          <Mic className="w-4 h-4" />
          New practice interview
        </Link>
      </div>

      {/* KPI row */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-muted-foreground font-medium">Latest score</span>
            <Target className="w-4 h-4 text-primary" />
          </div>
          {statsLoading ? (
            <Skeleton className="h-9 w-16" />
          ) : (
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-display font-bold text-foreground">
                {latestScore != null ? Math.round(latestScore) : "—"}
              </span>
              {trendDelta != null && (
                <span className={`text-xs font-medium ${trendDelta >= 0 ? "text-success" : "text-error"}`}>
                  {trendDelta >= 0 ? "+" : ""}
                  {trendDelta} pts
                </span>
              )}
            </div>
          )}
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-muted-foreground font-medium">Interviews done</span>
            <Sparkles className="w-4 h-4 text-accent" />
          </div>
          {statsLoading ? (
            <Skeleton className="h-9 w-12" />
          ) : (
            <span className="text-3xl font-display font-bold text-foreground">
              {stats?.totalCompletedInterviews ?? 0}
            </span>
          )}
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-muted-foreground font-medium">Weakest area</span>
            <TrendingUp className="w-4 h-4 text-warning" />
          </div>
          {statsLoading ? (
            <Skeleton className="h-7 w-24" />
          ) : (
            <span className="text-lg font-display font-semibold text-foreground capitalize">
              {stats?.weakestDimension ?? "—"}
            </span>
          )}
        </Card>

        <Card className="p-5 sm:col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted-foreground font-medium">Recommended next</span>
          </div>
          {statsLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (
            <p className="text-sm text-foreground leading-snug">
              {stats?.recommendedPractice ?? "Run a few interviews to get a personalized recommendation."}
            </p>
          )}
        </Card>
      </div>

      {/* Recent sessions */}
      <Card>
        <div className="flex items-center justify-between p-5 pb-0">
          <h2 className="font-display font-semibold text-foreground">Recent interviews</h2>
          <Link href="/candidate/history" className="text-xs text-primary hover:text-primary/80 transition-colors flex items-center gap-1">
            View all <ChevronRight className="w-3 h-3" />
          </Link>
        </div>
        <CardContent className="pt-4">
          {sessionsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : recentSessions.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <div className="p-3 rounded-full bg-primary/10">
                <Mic className="w-5 h-5 text-primary" />
              </div>
              <p className="text-sm text-muted-foreground">No interviews yet — your first one is two minutes away.</p>
              <Link href="/candidate/practice" className="text-sm text-primary hover:text-primary/80 font-medium transition-colors">
                Start practicing →
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {recentSessions.map((session) => (
                <Link
                  key={session.id}
                  href={
                    hasSessionReport(session.status)
                      ? `/candidate/interview/${session.id}/report`
                      : `/candidate/interview/${session.id}`
                  }
                  className="flex items-center gap-4 py-3.5 hover:bg-white/[0.02] -mx-1 px-1 rounded-lg transition-colors"
                >
                  <ScoreRing score={session.overallScore} size={44} strokeWidth={4} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {session.targetRoleTitle ?? "General Interview"}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-muted-foreground capitalize">{session.mode.replace("_", " ")}</span>
                      <span className="text-muted-foreground/40">·</span>
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {formatTimeAgo(session.createdAt)}
                      </span>
                    </div>
                  </div>
                  <Badge variant={sessionStatusVariant[session.status] === "success" ? "success" : "default"}>
                    {capitalize(session.status)}
                  </Badge>
                  <ArrowRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
