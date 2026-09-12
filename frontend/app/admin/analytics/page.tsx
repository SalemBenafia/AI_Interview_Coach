"use client";

import {
  Coins, Bot, CheckCircle2, Gauge, Smile,
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useApiQuery } from "@/hooks/use-api";
import { adminAnalyticsService } from "@/lib/api/services";
import { Card, CardContent, CardHeader, CardTitle, StatCard, Skeleton } from "@/components/ui";
import { capitalize } from "@/lib/utils/utils";
import type { AgentPerformance, PlatformOverview, SentimentDistributionEntry, TokenUsage } from "@/types";

// Matches this app's --chart-1..--chart-5 tokens (styles/globals.css) — the
// design system's fixed categorical order. Never cycled or generated; a 6th+
// category folds into "Other" rather than getting an invented hue.
const CHART_COLORS = [
  "hsl(156 100% 50%)",
  "hsl(172 78% 60%)",
  "hsl(38 95% 58%)",
  "hsl(280 80% 70%)",
  "hsl(340 80% 65%)",
];

const chartTooltipStyle = {
  background: "hsl(150 22% 8%)",
  border: "1px solid hsl(150 30% 16%)",
  borderRadius: 8,
  fontSize: 12,
} as const;

export default function AdminAnalyticsPage() {
  const { data: overview, isLoading: overviewLoading } = useApiQuery<PlatformOverview>({
    url: "/admin/analytics/overview/",
  });
  const { data: tokenUsage, isLoading: tokenLoading } = useApiQuery<TokenUsage>({
    url: "/admin/analytics/token-usage/",
    params: { days: 30 },
  });
  const { data: agentPerformance, isLoading: perfLoading } = useApiQuery<AgentPerformance[]>({
    url: "/admin/analytics/agent-performance/",
  });
  const { data: sentiment, isLoading: sentimentLoading } = useApiQuery<SentimentDistributionEntry[]>({
    url: "/admin/analytics/sentiment-distribution/",
    params: { days: 30 },
  });

  const totalTokens30d = tokenUsage?.dailyTotals.reduce((sum, d) => sum + d.totalTokens, 0) ?? null;
  const totalCalls = agentPerformance?.reduce((sum, a) => sum + a.calls, 0) ?? null;
  const weightedSuccessRate =
    agentPerformance && agentPerformance.length > 0
      ? (() => {
          const calls = agentPerformance.reduce((sum, a) => sum + a.calls, 0);
          if (!calls) return null;
          const successes = agentPerformance.reduce(
            (sum, a) => sum + (a.successRate != null ? (a.successRate / 100) * a.calls : 0),
            0
          );
          return Math.round((successes / calls) * 100 * 10) / 10;
        })()
      : null;

  // tokenUsage.byAgent is grouped by (agentKey, modelName) on the backend --
  // real data, since the Groq fallback chain can serve one agent through
  // several models -- but this chart is titled "by agent", so aggregate
  // across models here rather than showing multiple bars for the same
  // agent. The per-model split is still available in the tooltip.
  const tokenUsageByAgent = Object.values(
    (tokenUsage?.byAgent ?? []).reduce<Record<string, { agentKey: string; totalTokens: number; calls: number; models: string[] }>>(
      (acc, row) => {
        const existing = acc[row.agentKey];
        if (existing) {
          existing.totalTokens += row.totalTokens;
          existing.calls += row.calls;
          existing.models.push(row.modelName);
        } else {
          acc[row.agentKey] = { agentKey: row.agentKey, totalTokens: row.totalTokens, calls: row.calls, models: [row.modelName] };
        }
        return acc;
      },
      {}
    )
  );

  // Top 5 by count get their own slice; anything beyond that folds into
  // "Other" rather than generating a 6th+ hue (dataviz non-negotiable).
  const sentimentSorted = [...(sentiment ?? [])].sort((a, b) => b.count - a.count);
  const sentimentTop = sentimentSorted.slice(0, 5);
  const sentimentOther = sentimentSorted.slice(5);
  const sentimentOtherTotal = sentimentOther.reduce((sum, s) => sum + s.count, 0);
  const sentimentChartData = [
    ...sentimentTop.map((s) => ({ label: capitalize(s.label), value: s.count, percentage: s.percentage })),
    ...(sentimentOtherTotal > 0
      ? [{
          label: "Other",
          value: sentimentOtherTotal,
          percentage: Math.round((sentimentOtherTotal / sentimentSorted.reduce((s, x) => s + x.count, 0)) * 1000) / 10,
        }]
      : []),
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">AI analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Token usage, per-agent performance, and candidate sentiment — the AI-cost and quality signals that
          don't live on the platform overview dashboard.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Tokens used (30d)"
          value={totalTokens30d != null ? totalTokens30d.toLocaleString() : "—"}
          icon={<Coins className="w-5 h-5" />}
          loading={tokenLoading}
          color="primary"
        />
        <StatCard
          title="Agent calls (all-time)"
          value={totalCalls != null ? totalCalls.toLocaleString() : "—"}
          icon={<Bot className="w-5 h-5" />}
          loading={perfLoading}
          color="accent"
        />
        <StatCard
          title="Success rate"
          value={weightedSuccessRate != null ? `${weightedSuccessRate}%` : "—"}
          icon={<CheckCircle2 className="w-5 h-5" />}
          loading={perfLoading}
          color={weightedSuccessRate != null && weightedSuccessRate < 95 ? "warning" : "primary"}
        />
        <StatCard
          title="Avg AI latency"
          value={overview?.avgAiLatencyMs != null ? `${Math.round(overview.avgAiLatencyMs)}ms` : "—"}
          icon={<Gauge className="w-5 h-5" />}
          loading={overviewLoading}
          color={overview?.avgAiLatencyMs && overview.avgAiLatencyMs > 2000 ? "warning" : "accent"}
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Token usage — last 30 days</CardTitle>
          </CardHeader>
          <CardContent>
            {tokenLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : !tokenUsage || tokenUsage.dailyTotals.length === 0 ? (
              <EmptyState label="No token usage recorded yet." />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={tokenUsage.dailyTotals}>
                  <defs>
                    <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS[0]} stopOpacity={0.35} />
                      <stop offset="95%" stopColor={CHART_COLORS[0]} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(150 30% 16%)" vertical={false} />
                  <XAxis dataKey="date" stroke="hsl(138 14% 58%)" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="hsl(138 14% 58%)" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Area
                    type="monotone"
                    dataKey="totalTokens"
                    stroke={CHART_COLORS[0]}
                    fill="url(#colorTokens)"
                    strokeWidth={2}
                    name="Tokens"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Token usage by agent</CardTitle>
          </CardHeader>
          <CardContent>
            {tokenLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : tokenUsageByAgent.length === 0 ? (
              <EmptyState label="No token usage recorded yet." />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={tokenUsageByAgent}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(150 30% 16%)" vertical={false} />
                  <XAxis
                    dataKey="agentKey"
                    stroke="hsl(138 14% 58%)"
                    fontSize={11}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v: string) => capitalize(v)}
                  />
                  <YAxis stroke="hsl(138 14% 58%)" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={chartTooltipStyle}
                    labelFormatter={(v) => (typeof v === "string" ? capitalize(v) : v)}
                    formatter={(value, _name, item) => [
                      `${value} tokens (${(item.payload as { models: string[] }).models.join(", ")})`,
                      "Total",
                    ]}
                  />
                  <Bar dataKey="totalTokens" name="Tokens" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Per-agent performance</CardTitle>
          </CardHeader>
          <CardContent>
            {perfLoading ? (
              <Skeleton className="h-48 w-full" />
            ) : !agentPerformance || agentPerformance.length === 0 ? (
              <EmptyState label="No agent executions recorded yet." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b border-border">
                      <th className="font-medium py-2 pr-4">Agent</th>
                      <th className="font-medium py-2 pr-4">Calls</th>
                      <th className="font-medium py-2 pr-4">Avg latency</th>
                      <th className="font-medium py-2">Success rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agentPerformance.map((row) => (
                      <tr key={row.agentKey} className="border-b border-border last:border-0">
                        <td className="py-2.5 pr-4 text-foreground capitalize">{row.agentKey}</td>
                        <td className="py-2.5 pr-4 text-muted-foreground">{row.calls.toLocaleString()}</td>
                        <td className="py-2.5 pr-4 text-muted-foreground">
                          {row.avgLatencyMs != null ? `${Math.round(row.avgLatencyMs)}ms` : "—"}
                        </td>
                        <td
                          className={
                            row.successRate != null && row.successRate < 95
                              ? "py-2.5 text-warning font-medium"
                              : "py-2.5 text-muted-foreground"
                          }
                        >
                          {row.successRate != null ? `${row.successRate}%` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Smile className="w-4 h-4 text-primary" /> Candidate sentiment — last 30 days
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sentimentLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : sentimentChartData.length === 0 ? (
              <EmptyState label="No sentiment data recorded yet — check the sentiment service is running." />
            ) : (
              <div className="flex items-center gap-6">
                <ResponsiveContainer width="60%" height={220}>
                  <PieChart>
                    <Pie data={sentimentChartData} dataKey="value" nameKey="label" innerRadius={50} outerRadius={80} paddingAngle={2}>
                      {sentimentChartData.map((entry, i) => (
                        <Cell key={entry.label} fill={CHART_COLORS[i % CHART_COLORS.length]} stroke="hsl(150 22% 7%)" strokeWidth={2} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={chartTooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <ul className="space-y-1.5 flex-1 min-w-0">
                  {sentimentChartData.map((entry, i) => (
                    <li key={entry.label} className="flex items-center gap-2 text-xs">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                      />
                      <span className="text-foreground truncate">{entry.label}</span>
                      <span className="text-muted-foreground ml-auto flex-shrink-0">{entry.percentage}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="h-48 flex items-center justify-center text-center px-6">
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
