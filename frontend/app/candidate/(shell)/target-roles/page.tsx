"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Briefcase, Plus, ChevronRight, Sparkles, Loader2, AlertCircle } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useApiQuery, useApiMutation } from "@/hooks/use-api";
import { targetRolesService } from "@/lib/api/services";
import { Card, Badge, Skeleton, Button, Modal, Input, Textarea } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";
import type { CandidateTargetRole, TargetRoleStatus } from "@/types";

const STATUS_BADGE: Record<TargetRoleStatus, { variant: "success" | "warning" | "error" | "default"; label: string }> = {
  draft: { variant: "default", label: "Draft" },
  analyzing: { variant: "warning", label: "Analyzing…" },
  ready: { variant: "success", label: "Ready" },
  failed: { variant: "error", label: "Analysis failed" },
};

export default function TargetRolesPage() {
  const router = useRouter();
  const { data: roles, isLoading } = useApiQuery<CandidateTargetRole[]>({ url: "/target-roles/" });
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Your target roles</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Create one for each job you're preparing for. Add your own background, and the AI turns it into
            private knowledge it draws on during your interviews — nobody else can see or edit this.
          </p>
        </div>
        <Button leftIcon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>
          New target role
        </Button>
      </div>

      {isLoading ? (
        <div className="grid sm:grid-cols-2 gap-4">
          {[1, 2].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : !roles || roles.length === 0 ? (
        <Card className="p-12 text-center">
          <Briefcase className="w-6 h-6 text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-foreground font-medium">No target roles yet</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            Create one to tell the AI about the role you're preparing for and your own background — it'll ask
            you grounded, relevant questions instead of generic ones.
          </p>
        </Card>
      ) : (
        <div className="grid sm:grid-cols-2 gap-4">
          {roles.map((role) => {
            const badge = STATUS_BADGE[role.status];
            return (
              <button
                key={role.id}
                type="button"
                onClick={() => router.push(`/candidate/target-roles/${role.id}`)}
                className="text-left"
              >
                <Card className="p-5 h-full hover:border-primary/30 transition-colors flex flex-col">
                  <div className="flex items-start justify-between mb-2">
                    <Badge variant={badge.variant}>{badge.label}</Badge>
                    {role.status === "analyzing" && <Loader2 className="w-3.5 h-3.5 text-warning animate-spin" />}
                    {role.status === "failed" && <AlertCircle className="w-3.5 h-3.5 text-error" />}
                  </div>
                  <h3 className="font-display font-semibold text-foreground">{role.title}</h3>
                  {role.description && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2 flex-1">{role.description}</p>
                  )}
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-border">
                    <span className="text-xs text-muted-foreground">
                      {(role.fields?.length ?? 0) > 0 ? `${role.fields?.length} field(s)` : "No fields yet"}
                    </span>
                    <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                  </div>
                </Card>
              </button>
            );
          })}
        </div>
      )}

      <CreateTargetRoleModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}

function CreateTargetRoleModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const createMutation = useApiMutation<{ targetRoleId: string }, { title: string; description?: string }>({
    url: "/target-roles/",
    onSuccess: (data) => {
      toast.success("Target role created");
      queryClient.invalidateQueries({ queryKey: ["/target-roles/"] });
      setTitle("");
      setDescription("");
      onClose();
      router.push(`/candidate/target-roles/${data.targetRoleId}`);
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="New target role" description="Give it a name — you'll add background details next." size="sm">
      <div className="p-6 pt-0 space-y-4">
        <Input
          label="Job title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Senior Backend Engineer"
        />
        <Textarea
          label="Short description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="A sentence or two about the role, if useful."
          rows={3}
        />
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            leftIcon={<Sparkles className="w-4 h-4" />}
            loading={createMutation.isPending}
            disabled={!title.trim()}
            onClick={() => createMutation.mutate({ title: title.trim(), description: description.trim() || undefined })}
          >
            Create
          </Button>
        </div>
      </div>
    </Modal>
  );
}
