"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Briefcase, ChevronDown, ChevronUp, BookOpen } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api";
import { adminUsersService } from "@/lib/api/services";
import { Card, CardContent, Badge, Skeleton } from "@/components/ui";
import { formatDate, formatTimeAgo } from "@/lib/utils/format";
import { capitalize } from "@/lib/utils/utils";
import type { AdminCandidateRow, CandidateTargetRole } from "@/types";

const TARGET_ROLE_BADGE: Record<string, "success" | "warning" | "error" | "default"> = {
  draft: "default",
  analyzing: "warning",
  ready: "success",
  failed: "error",
};

export default function AdminCandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const router = useRouter();

  const { data: candidate, isLoading: candidateLoading } = useApiQuery<AdminCandidateRow>({
    url: `/admin/users/${params.candidateId}/`,
  });
  const { data: sessions, isLoading: sessionsLoading } = useApiQuery({
    url: `/admin/users/${params.candidateId}/sessions/`,
  });
  const { data: targetRoles, isLoading: targetRolesLoading } = useApiQuery<CandidateTargetRole[]>({
    url: `/admin/users/${params.candidateId}/target-roles/`,
  });

  if (candidateLoading || !candidate) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.push("/admin/users")}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-display font-bold text-foreground">
              {candidate.firstName} {candidate.lastName}
            </h1>
            <Badge variant={candidate.isActive ? "success" : "error"}>
              {candidate.isActive ? "Active" : "Suspended"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">{candidate.email}</p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <Card className="p-4">
          <p className="text-2xs uppercase tracking-wider text-muted-foreground">Last login</p>
          <p className="text-sm text-foreground mt-1">{formatTimeAgo(candidate.lastLoginAt)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-2xs uppercase tracking-wider text-muted-foreground">Joined</p>
          <p className="text-sm text-foreground mt-1">{formatDate(candidate.createdAt)}</p>
        </Card>
      </div>

      {/* Target roles + knowledge (read-only admin visibility) */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Briefcase className="w-4 h-4" />
          Target roles
        </h2>
        {targetRolesLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : !targetRoles || targetRoles.length === 0 ? (
          <Card className="p-6 text-center">
            <p className="text-xs text-muted-foreground">This candidate hasn't created any target roles yet.</p>
          </Card>
        ) : (
          <div className="space-y-2">
            {targetRoles.map((role) => (
              <TargetRoleRow key={role.id} candidateId={params.candidateId} role={role} />
            ))}
          </div>
        )}
      </div>

      {/* Session history */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Session history</h2>
        <Card>
          {sessionsLoading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !sessions || (sessions as any[]).length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">No sessions yet.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground uppercase tracking-wider">
                  <th className="px-5 py-3 font-medium">Target role</th>
                  <th className="px-5 py-3 font-medium">Mode</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Score</th>
                  <th className="px-5 py-3 font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(sessions as any[]).map((s) => (
                  <tr key={s.id}>
                    <td className="px-5 py-3 text-foreground">{s.targetRoleTitle ?? "General"}</td>
                    <td className="px-5 py-3 text-muted-foreground capitalize">{s.mode.replace("_", " ")}</td>
                    <td className="px-5 py-3">
                      <Badge variant={s.status === "completed" ? "success" : "default"}>{capitalize(s.status)}</Badge>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">{s.overallScore ?? "—"}</td>
                    <td className="px-5 py-3 text-muted-foreground">{formatDate(s.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}

function TargetRoleRow({ candidateId, role }: { candidateId: string; role: CandidateTargetRole }) {
  const [expanded, setExpanded] = useState(false);

  const { data: detail } = useApiQuery<CandidateTargetRole>({
    url: `/admin/users/${candidateId}/target-roles/${role.id}/`,
    enabled: expanded,
  });
  const { data: knowledge } = useApiQuery({
    url: `/admin/users/${candidateId}/target-roles/${role.id}/knowledge/`,
    enabled: expanded && role.status === "ready",
  });

  return (
    <Card>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-foreground">{role.title}</p>
          <Badge variant={TARGET_ROLE_BADGE[role.status] ?? "default"}>{capitalize(role.status)}</Badge>
        </div>
        {expanded ? (
          <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
        )}
      </button>
      {expanded && (
        <CardContent className="px-4 pb-4 pt-0 space-y-4 border-t border-border">
          <div className="pt-4">
            <p className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              Candidate's own fields
            </p>
            {!detail ? (
              <Skeleton className="h-16 w-full" />
            ) : (detail.fields ?? []).length === 0 ? (
              <p className="text-xs text-muted-foreground">No fields added yet.</p>
            ) : (
              <div className="space-y-2">
                {(detail.fields ?? []).map((f) => (
                  <div key={f.id} className="rounded-lg border border-border p-3">
                    <p className="text-xs font-medium text-foreground">{f.fieldTitle}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{f.fieldDescription}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {role.status === "ready" && (
            <div>
              <p className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                <BookOpen className="w-3 h-3" />
                Extracted knowledge
              </p>
              {!knowledge ? (
                <Skeleton className="h-16 w-full" />
              ) : (knowledge as any[]).length === 0 ? (
                <p className="text-xs text-muted-foreground">No knowledge entries.</p>
              ) : (
                <div className="grid sm:grid-cols-2 gap-2">
                  {(knowledge as any[]).map((entry) => (
                    <div key={entry.id} className="rounded-lg border border-border p-3">
                      <Badge variant="default">{capitalize(entry.category)}</Badge>
                      <p className="text-xs font-medium text-foreground mt-1">{entry.topic}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{entry.summary}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
