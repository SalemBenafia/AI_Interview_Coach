"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, Plus, Trash2, Sparkles, Loader2, CheckCircle2, AlertCircle, BookOpen,
} from "lucide-react";
import { useApiQuery, useApiMutation } from "@/hooks/use-api";
import { targetRolesService } from "@/lib/api/services";
import { Card, CardContent, Badge, Skeleton, Button, Input, Textarea, Modal } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";
import { capitalize } from "@/lib/utils/utils";
import type { CandidateKnowledgeEntry, CandidateTargetRole, CandidateTargetRoleField } from "@/types";

const STATUS_BADGE: Record<string, { variant: "success" | "warning" | "error" | "default"; label: string }> = {
  draft: { variant: "default", label: "Draft" },
  analyzing: { variant: "warning", label: "Analyzing…" },
  ready: { variant: "success", label: "Ready" },
  failed: { variant: "error", label: "Analysis failed" },
};

export default function TargetRoleDetailPage() {
  const params = useParams<{ targetRoleId: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: role, isLoading } = useApiQuery<CandidateTargetRole>({
    url: `/target-roles/${params.targetRoleId}/`,
    refetchInterval: (query) => (query.state.data?.status === "analyzing" ? 2000 : false),
  });

  const { data: knowledge } = useApiQuery<CandidateKnowledgeEntry[]>({
    url: `/target-roles/${params.targetRoleId}/knowledge/`,
    enabled: role?.status === "ready",
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: [`/target-roles/${params.targetRoleId}/`] });

  const addFieldMutation = useApiMutation<{ fieldId: string }, { field_title: string; field_description: string }>({
    url: `/target-roles/${params.targetRoleId}/fields/`,
    onSuccess: invalidate,
  });

  const updateFieldMutation = useApiMutation<unknown, { fieldId: string; field_title?: string; field_description?: string }>({
    url: (vars) => `/target-roles/${params.targetRoleId}/fields/${vars.fieldId}/`,
    method: "patch",
    onSuccess: invalidate,
  });

  const deleteFieldMutation = useApiMutation<unknown, { fieldId: string }>({
    url: (vars) => `/target-roles/${params.targetRoleId}/fields/${vars.fieldId}/`,
    method: "delete",
    onSuccess: invalidate,
  });

  const analyzeMutation = useApiMutation<{ status: string }, void>({
    url: `/target-roles/${params.targetRoleId}/analyze/`,
    onSuccess: () => {
      toast.success("Analyzing your background…", "This usually takes a few seconds.");
      invalidate();
    },
    onError: () => toast.error("Couldn't start analysis", "Please try again."),
  });

  const [newFieldTitle, setNewFieldTitle] = useState("");
  const [newFieldDescription, setNewFieldDescription] = useState("");
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingRole, setDeletingRole] = useState(false);

  const handleDeleteRole = async () => {
    setDeletingRole(true);
    try {
      await targetRolesService.remove(params.targetRoleId);
      toast.success("Target role deleted");
      queryClient.invalidateQueries({ queryKey: ["/target-roles/"] });
      router.push("/candidate/target-roles");
    } catch {
      toast.error("Couldn't delete this target role");
      setDeletingRole(false);
    }
  };

  if (isLoading || !role) {
    return (
      <div className="max-w-3xl mx-auto space-y-4 animate-fade-in">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const badge = STATUS_BADGE[role.status];
  const fields = role.fields ?? [];

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.push("/candidate/target-roles")}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-display font-bold text-foreground truncate">{role.title}</h1>
            <Badge variant={badge.variant}>{badge.label}</Badge>
          </div>
          {role.description && <p className="text-sm text-muted-foreground mt-0.5">{role.description}</p>}
        </div>
        <button
          type="button"
          onClick={() => setDeleteConfirmOpen(true)}
          className="p-2 text-muted-foreground hover:text-error transition-colors flex-shrink-0"
          title="Delete this target role"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <Modal
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        title="Delete this target role?"
        description="This permanently removes it, along with all its fields and any knowledge the AI extracted from them. This cannot be undone."
        size="sm"
      >
        <div className="p-6 pt-0 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setDeleteConfirmOpen(false)}>
            Cancel
          </Button>
          <Button variant="danger" loading={deletingRole} onClick={handleDeleteRole}>
            Delete
          </Button>
        </div>
      </Modal>

      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Your background for this role</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Add as many fields as you like — experience, projects, skills, anything relevant. The AI reads
                these to ground your interview questions in your own real background.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {fields.map((field) => (
              <FieldRow
                key={field.id}
                field={field}
                onSave={(payload) => updateFieldMutation.mutate({ fieldId: field.id, ...payload })}
                onDelete={() => deleteFieldMutation.mutate({ fieldId: field.id })}
              />
            ))}
          </div>

          <div className="rounded-lg border border-dashed border-border p-4 space-y-3">
            <Input
              label="Field title"
              value={newFieldTitle}
              onChange={(e) => setNewFieldTitle(e.target.value)}
              placeholder="e.g. Experience"
            />
            <Textarea
              label="Field description"
              value={newFieldDescription}
              onChange={(e) => setNewFieldDescription(e.target.value)}
              placeholder="e.g. Worked at Acme as a backend developer for 2 years, building payments infrastructure."
              rows={3}
            />
            <Button
              variant="outline"
              size="sm"
              leftIcon={<Plus className="w-3.5 h-3.5" />}
              disabled={!newFieldTitle.trim() || !newFieldDescription.trim()}
              loading={addFieldMutation.isPending}
              onClick={() => {
                addFieldMutation.mutate({
                  field_title: newFieldTitle.trim(),
                  field_description: newFieldDescription.trim(),
                });
                setNewFieldTitle("");
                setNewFieldDescription("");
              }}
            >
              Add field
            </Button>
          </div>

          <div className="pt-2 border-t border-border flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              {fields.length === 0
                ? "Add at least one field before analyzing."
                : `${fields.length} field(s) ready to analyze.`}
            </p>
            <Button
              leftIcon={
                role.status === "analyzing" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )
              }
              disabled={fields.length === 0 || role.status === "analyzing"}
              loading={analyzeMutation.isPending}
              onClick={() => analyzeMutation.mutate()}
            >
              {role.status === "ready" ? "Re-analyze" : "Analyze"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {role.status === "ready" && (
        <Card>
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-primary" />
              <h2 className="text-sm font-semibold text-foreground">What the AI learned</h2>
            </div>
            {!knowledge ? (
              <Skeleton className="h-24 w-full" />
            ) : knowledge.length === 0 ? (
              <p className="text-xs text-muted-foreground">No knowledge entries yet.</p>
            ) : (
              <div className="grid sm:grid-cols-2 gap-3">
                {knowledge.map((entry) => (
                  <div key={entry.id} className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between mb-1">
                      <Badge variant="default">{capitalize(entry.category)}</Badge>
                    </div>
                    <p className="text-sm font-medium text-foreground">{entry.topic}</p>
                    <p className="text-xs text-muted-foreground mt-1">{entry.summary}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {role.status === "failed" && (
        <Card className="border-error/30">
          <CardContent className="p-5 flex items-start gap-3">
            <AlertCircle className="w-4 h-4 text-error mt-0.5" />
            <div>
              <p className="text-sm font-medium text-foreground">Analysis failed</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Something went wrong extracting knowledge from your fields. Try again, or adjust your fields
                and re-analyze.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {role.status === "ready" && (
        <div className="flex items-center gap-2 text-xs text-success">
          <CheckCircle2 className="w-3.5 h-3.5" />
          This target role is ready to use — select it next time you start a practice interview.
        </div>
      )}
    </div>
  );
}

function FieldRow({
  field,
  onSave,
  onDelete,
}: {
  field: CandidateTargetRoleField;
  onSave: (payload: { field_title?: string; field_description?: string }) => void;
  onDelete: () => void;
}) {
  const [title, setTitle] = useState(field.fieldTitle);
  const [description, setDescription] = useState(field.fieldDescription);

  return (
    <div className="rounded-lg border border-border p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => title !== field.fieldTitle && onSave({ field_title: title })}
          className="flex-1"
        />
        <button
          type="button"
          onClick={onDelete}
          className="p-2 text-muted-foreground hover:text-error transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      <Textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        onBlur={() => description !== field.fieldDescription && onSave({ field_description: description })}
        rows={2}
      />
    </div>
  );
}
