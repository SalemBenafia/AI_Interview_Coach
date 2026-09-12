"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, UserX, UserCheck, Trash2 } from "lucide-react";
import { useApiPaginated, useApiMutation } from "@/hooks/use-api";
import { Card, Badge, Skeleton, Pagination, Input } from "@/components/ui";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useToast } from "@/store/use-ui-store";
import { formatDate, formatTimeAgo } from "@/lib/utils/format";
import { debounce } from "@/lib/utils/utils";
import type { AdminCandidateRow } from "@/types";

export default function AdminUsersPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [confirmAction, setConfirmAction] = useState<{ id: string; type: "suspend" | "delete" } | null>(null);
  const { toast } = useToast();
  const limit = 15;

  const { data, isLoading, refetch } = useApiPaginated<AdminCandidateRow>({
    url: "/admin/users/",
    params: { page, limit, ...(search ? { search } : {}) },
  });

  const suspendMutation = useApiMutation<unknown, { id: string }>({
    url: (vars) => `/admin/users/${vars.id}/suspend/`,
    onSuccess: () => {
      toast.success("Candidate suspended");
      refetch();
    },
  });

  const activateMutation = useApiMutation<unknown, { id: string }>({
    url: (vars) => `/admin/users/${vars.id}/activate/`,
    onSuccess: () => {
      toast.success("Candidate activated");
      refetch();
    },
  });

  const deleteMutation = useApiMutation<unknown, { id: string }>({
    url: (vars) => `/admin/users/${vars.id}/`,
    method: "delete",
    onSuccess: () => {
      toast.success("Candidate deleted");
      refetch();
    },
  });

  const debouncedSearch = debounce((value: string) => {
    setSearch(value);
    setPage(1);
  }, 350);

  const candidates = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Candidates</h1>
          <p className="text-sm text-muted-foreground mt-1">{meta?.total ?? 0} registered candidates</p>
        </div>
        <div className="w-64">
          <Input
            placeholder="Search by name or email…"
            leftIcon={<Search className="w-4 h-4" />}
            onChange={(e) => debouncedSearch(e.target.value)}
          />
        </div>
      </div>

      <Card>
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : candidates.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">No candidates found.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground uppercase tracking-wider">
                <th className="px-5 py-3 font-medium">Candidate</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Last login</th>
                <th className="px-5 py-3 font-medium">Joined</th>
                <th className="px-5 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {candidates.map((c) => (
                <tr key={c.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-3.5">
                    <Link href={`/admin/users/${c.id}`} className="hover:underline">
                      <p className="font-medium text-foreground">
                        {c.firstName} {c.lastName}
                      </p>
                      <p className="text-xs text-muted-foreground">{c.email}</p>
                    </Link>
                  </td>
                  <td className="px-5 py-3.5">
                    <Badge variant={c.isActive ? "success" : "error"}>{c.isActive ? "Active" : "Suspended"}</Badge>
                  </td>
                  <td className="px-5 py-3.5 text-muted-foreground">{formatTimeAgo(c.lastLoginAt)}</td>
                  <td className="px-5 py-3.5 text-muted-foreground">{formatDate(c.createdAt)}</td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center justify-end gap-1">
                      {c.isActive ? (
                        <button
                          type="button"
                          onClick={() => setConfirmAction({ id: c.id, type: "suspend" })}
                          className="p-1.5 rounded-md text-muted-foreground hover:text-warning hover:bg-warning/10 transition-colors"
                          title="Suspend"
                        >
                          <UserX className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => activateMutation.mutate({ id: c.id })}
                          className="p-1.5 rounded-md text-muted-foreground hover:text-success hover:bg-success/10 transition-colors"
                          title="Activate"
                        >
                          <UserCheck className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setConfirmAction({ id: c.id, type: "delete" })}
                        className="p-1.5 rounded-md text-muted-foreground hover:text-error hover:bg-error/10 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {meta && meta.total > 0 && (
          <Pagination page={meta.page} totalPages={meta.total_pages} total={meta.total} limit={meta.limit} onPageChange={setPage} />
        )}
      </Card>

      <ConfirmDialog
        open={!!confirmAction}
        onClose={() => setConfirmAction(null)}
        onConfirm={() => {
          if (!confirmAction) return;
          if (confirmAction.type === "suspend") suspendMutation.mutate({ id: confirmAction.id });
          if (confirmAction.type === "delete") deleteMutation.mutate({ id: confirmAction.id });
          setConfirmAction(null);
        }}
        title={confirmAction?.type === "delete" ? "Delete this candidate?" : "Suspend this candidate?"}
        description={
          confirmAction?.type === "delete"
            ? "This soft-deletes the account — their interview history is preserved but they can no longer sign in."
            : "They won't be able to sign in until reactivated."
        }
        confirmLabel={confirmAction?.type === "delete" ? "Delete" : "Suspend"}
        destructive
      />
    </div>
  );
}
