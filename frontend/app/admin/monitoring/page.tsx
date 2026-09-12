"use client";

import { Activity, CheckCircle2, XCircle, AlertTriangle, Radio } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle, Badge, Skeleton } from "@/components/ui";
import { formatTimeAgo } from "@/lib/utils/format";

interface LiveSession {
  id: string;
  status: string;
  candidateName: string;
  targetRoleTitle: string | null;
  mode: string;
  difficulty: string;
  questionsAsked: number;
  startedAt: string | null;
}

interface HealthResponse {
  overall: string;
  services: Record<string, { status: string; httpStatus?: number; detail?: string }>;
}

interface ErrorLog {
  id: string;
  sessionId: string | null;
  agentKey: string;
  errorMessage: string;
  timestamp: string;
}

export default function AdminMonitoringPage() {
  const { data: liveSessions, isLoading: sessionsLoading } = useApiQuery<LiveSession[]>({
    url: "/admin/monitoring/live-sessions/",
    refetchInterval: 8000,
  });
  const { data: health, isLoading: healthLoading } = useApiQuery<HealthResponse>({
    url: "/admin/monitoring/health/",
    refetchInterval: 15000,
  });
  const { data: errorLogs, isLoading: logsLoading } = useApiQuery<ErrorLog[]>({ url: "/admin/monitoring/error-logs/" });

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Monitoring</h1>
        <p className="text-sm text-muted-foreground mt-1">Live sessions, service health, and recent errors.</p>
      </div>

      {/* System health */}
      <Card>
        <CardHeader>
          <CardTitle>System health</CardTitle>
        </CardHeader>
        <CardContent>
          {healthLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="grid sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {Object.entries(health?.services ?? {}).map(([name, info]) => (
                <div key={name} className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-white/[0.02] border border-border">
                  {info.status === "ok" ? (
                    <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0" />
                  ) : info.status === "degraded" ? (
                    <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-error flex-shrink-0" />
                  )}
                  <span className="text-sm text-foreground capitalize truncate">{name.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Live sessions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-success" /> Live sessions
          </CardTitle>
        </CardHeader>
        <CardContent>
          {sessionsLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : !liveSessions || liveSessions.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">No active interviews right now.</p>
          ) : (
            <div className="divide-y divide-border">
              {liveSessions.map((s) => (
                <div key={s.id} className="flex items-center gap-4 py-3">
                  <div className="live-indicator flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{s.candidateName}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.targetRoleTitle ?? "General"} · {s.mode} · {s.difficulty} · Q{s.questionsAsked}
                    </p>
                  </div>
                  <Badge variant={s.status === "active" ? "success" : "warning"}>{s.status}</Badge>
                  <span className="text-xs text-muted-foreground flex-shrink-0">{formatTimeAgo(s.startedAt)}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error logs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-error" /> Recent errors
          </CardTitle>
        </CardHeader>
        <CardContent>
          {logsLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : !errorLogs || errorLogs.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">No errors recorded.</p>
          ) : (
            <div className="divide-y divide-border">
              {errorLogs.map((log) => (
                <div key={log.id} className="py-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="error">{log.agentKey}</Badge>
                    <span className="text-xs text-muted-foreground">{formatTimeAgo(log.timestamp)}</span>
                  </div>
                  <p className="text-sm text-foreground mt-1.5 font-mono-coach text-xs">{log.errorMessage}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
