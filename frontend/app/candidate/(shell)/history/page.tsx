"use client";

import { useState } from "react";
import Link from "next/link";
import { Mic, Clock, ChevronRight } from "lucide-react";
import { useApiPaginated } from "@/hooks/use-api";
import { Card, Badge, Skeleton, Select, Pagination, ScoreRing } from "@/components/ui";
import { capitalize, hasSessionReport, sessionStatusVariant } from "@/lib/utils/utils";
import { formatDate, formatDuration } from "@/lib/utils/format";
import type { InterviewSession } from "@/types";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "completed", label: "Completed" },
  { value: "abandoned", label: "Abandoned" },
  { value: "active", label: "Active" },
];

export default function HistoryPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const limit = 10;

  const { data, isLoading } = useApiPaginated<InterviewSession>({
    url: "/interviews/sessions/",
    params: { page, limit, ...(status ? { status } : {}) },
  });

  const sessions = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Interview history</h1>
          <p className="text-sm text-muted-foreground mt-1">Every practice session, scored and saved.</p>
        </div>
        <div className="w-48">
          <Select
            options={STATUS_OPTIONS.filter((o) => o.value !== "")}
            placeholder="All statuses"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      <Card>
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <div className="p-3 rounded-full bg-primary/10">
              <Mic className="w-5 h-5 text-primary" />
            </div>
            <p className="text-sm text-muted-foreground">No interviews match this filter yet.</p>
            <Link href="/candidate/practice" className="text-sm text-primary hover:text-primary/80 font-medium transition-colors">
              Start practicing →
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {sessions.map((session) => (
              <Link
                key={session.id}
                href={
                  hasSessionReport(session.status)
                    ? `/candidate/interview/${session.id}/report`
                    : `/candidate/interview/${session.id}`
                }
                className="flex items-center gap-4 px-5 py-4 hover:bg-white/[0.02] transition-colors"
              >
                <ScoreRing score={session.overallScore} size={48} strokeWidth={4} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {session.targetRoleTitle ?? "General Interview"}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className="text-xs text-muted-foreground capitalize">{session.mode.replace("_", " ")}</span>
                    <span className="text-muted-foreground/40">·</span>
                    <span className="text-xs text-muted-foreground capitalize">{session.difficulty}</span>
                    <span className="text-muted-foreground/40">·</span>
                    <span className="text-xs text-muted-foreground">{formatDate(session.createdAt)}</span>
                    {session.durationSeconds != null && (
                      <>
                        <span className="text-muted-foreground/40">·</span>
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <Clock className="w-3 h-3" /> {formatDuration(session.durationSeconds)}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <Badge variant={sessionStatusVariant[session.status] === "success" ? "success" : "default"}>
                  {capitalize(session.status)}
                </Badge>
                <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              </Link>
            ))}
          </div>
        )}

        {meta && meta.total > 0 && (
          <Pagination page={meta.page} totalPages={meta.total_pages} total={meta.total} limit={meta.limit} onPageChange={setPage} />
        )}
      </Card>
    </div>
  );
}
