"use client";

import {
  Users, Mic, TrendingUp, Gauge, Star, Activity,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useApiQuery } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, StatCard, Skeleton } from "@/components/ui";
import type { PlatformOverview, TrendPoint } from "@/types";

export default function AdminDashboardPage() {
  const { data: overview, isLoading } = useApiQuery<PlatformOverview>({ url: "/admin/analytics/overview/" });
  const { data: trend, isLoading: trendLoading } = useApiQuery<TrendPoint[]>({
    url: "/admin/analytics/trend/",
    params: { days: 30 },
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Platform overview</h1>
        <p className="text-sm text-muted-foreground mt-1">Is the AI system performing well at scale?</p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total candidates" value={overview?.totalUsers ?? "—"} icon={<Users className="w-5 h-5" />} loading={isLoading} color="primary" />
        <StatCard
          title="Interviews (30d)"
          value={overview?.interviewsLast30Days ?? "—"}
          subtitle={`${overview?.completedInterviewsLast30Days ?? 0} completed`}
          icon={<Mic className="w-5 h-5" />}
          loading={isLoading}
          color="accent"
        />
        <StatCard
          title="Completion rate"
          value={overview?.completionRate != null ? `${overview.completionRate}%` : "—"}
          icon={<TrendingUp className="w-5 h-5" />}
          loading={isLoading}
          color="primary"
        />
        <StatCard
          title="Avg AI latency"
          value={overview?.avgAiLatencyMs != null ? `${Math.round(overview.avgAiLatencyMs)}ms` : "—"}
          icon={<Gauge className="w-5 h-5" />}
          loading={isLoading}
          color={overview?.avgAiLatencyMs && overview.avgAiLatencyMs > 2000 ? "warning" : "accent"}
        />
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <StatCard
          title="Avg overall score"
          value={overview?.avgOverallScore != null ? Math.round(overview.avgOverallScore) : "—"}
          icon={<Activity className="w-5 h-5" />}
          loading={isLoading}
        />
        <StatCard
          title="Avg feedback rating"
          value={overview?.avgFeedbackRating != null ? `${overview.avgFeedbackRating.toFixed(1)} / 5` : "—"}
          icon={<Star className="w-5 h-5" />}
          loading={isLoading}
          color="warning"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Interview volume — last 30 days</CardTitle>
        </CardHeader>
        <CardContent>
          {trendLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={trend ?? []}>
                <defs>
                  <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(156 100% 50%)" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="hsl(156 100% 50%)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorCompleted" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(172 78% 60%)" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="hsl(172 78% 60%)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(150 30% 16%)" vertical={false} />
                <XAxis dataKey="date" stroke="hsl(138 14% 58%)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="hsl(138 14% 58%)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(150 22% 8%)",
                    border: "1px solid hsl(150 30% 16%)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Area type="monotone" dataKey="totalInterviews" stroke="hsl(156 100% 50%)" fill="url(#colorTotal)" strokeWidth={2} name="Total" />
                <Area type="monotone" dataKey="completedInterviews" stroke="hsl(172 78% 60%)" fill="url(#colorCompleted)" strokeWidth={2} name="Completed" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
