"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useApiQuery, useApiMutation } from "@/hooks/use-api";
import { Card, Input, Skeleton } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";

interface DifficultyRuleRow {
  id: string; level: string; label: string; advanceScoreThreshold: number; regressScoreThreshold: number;
}

export default function AdminContentPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Difficulty scaling</h1>
        <p className="text-sm text-muted-foreground mt-1">
          The only content-authoring surface admins have — target roles and knowledge are candidate-owned,
          and interview behavior lives in AI Studio → Agents.
        </p>
      </div>

      <DifficultyTab />
    </div>
  );
}

function DifficultyTab() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { data: rules, isLoading } = useApiQuery<DifficultyRuleRow[]>({ url: "/admin/content/difficulty-rules/" });

  const updateMutation = useApiMutation<unknown, { level: string; advance_score_threshold: number; regress_score_threshold: number }>({
    url: (vars) => `/admin/content/difficulty-rules/${vars.level}/`,
    method: "patch",
    onSuccess: () => {
      toast.success("Updated");
      queryClient.invalidateQueries({ queryKey: ["/admin/content/difficulty-rules/"] });
    },
  });

  if (isLoading) return <Skeleton className="h-48 w-full" />;

  return (
    <div className="grid sm:grid-cols-3 gap-4">
      {(rules ?? []).map((rule) => (
        <Card key={rule.id} className="p-5">
          <h3 className="font-display font-semibold text-foreground capitalize mb-3">{rule.label}</h3>
          <div className="space-y-3">
            <Input
              label="Advance threshold (score >)"
              type="number"
              defaultValue={rule.advanceScoreThreshold}
              onBlur={(e) =>
                updateMutation.mutate({
                  level: rule.level,
                  advance_score_threshold: Number(e.target.value),
                  regress_score_threshold: rule.regressScoreThreshold,
                })
              }
            />
            <Input
              label="Coaching threshold (score <)"
              type="number"
              defaultValue={rule.regressScoreThreshold}
              onBlur={(e) =>
                updateMutation.mutate({
                  level: rule.level,
                  advance_score_threshold: rule.advanceScoreThreshold,
                  regress_score_threshold: Number(e.target.value),
                })
              }
            />
          </div>
        </Card>
      ))}
    </div>
  );
}
