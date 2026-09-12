"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GitBranch, Plus, ChevronRight, CheckCircle2, AlertTriangle, Radio } from "lucide-react";
import { useApiQuery, useApiMutation } from "@/hooks/use-api";
import { useQueryClient } from "@tanstack/react-query";
import { Card, Badge, Skeleton, Button } from "@/components/ui";
import { Modal, Input, Select, Toggle } from "@/components/ui";
import { cn, capitalize } from "@/lib/utils/utils";
import { useToast } from "@/store/use-ui-store";
import { useRouter } from "next/navigation";
import type { InterviewFlow, ModeOption } from "@/types";

export default function AdminFlowsPage() {
  const { data: flows, isLoading } = useApiQuery<InterviewFlow[]>({ url: "/admin/flows/" });
  const { data: modes, isLoading: modesLoading } = useApiQuery<ModeOption[]>({ url: "/catalog/modes/" });
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [createForMode, setCreateForMode] = useState<string | undefined>(undefined);

  const setDefaultMutation = useApiMutation<unknown, { id: string }>({
    url: (vars) => `/admin/flows/${vars.id}/set-default/`,
    onSuccess: () => {
      toast.success("This is now the live flow for its mode");
      queryClient.invalidateQueries({ queryKey: ["/admin/flows/"] });
    },
  });

  const loading = isLoading || modesLoading;

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">AI Studio — Flows</h1>
          <p className="text-sm text-muted-foreground mt-1">
            One global, published flow per interview mode actually drives every candidate's session in that
            mode — the <span className="text-success font-medium">Live</span> badge below shows which one.
          </p>
        </div>
        <Button
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={() => {
            setCreateForMode(undefined);
            setCreateOpen(true);
          }}
        >
          New flow
        </Button>
      </div>

      {loading ? (
        <div className="space-y-8">
          {[1, 2].map((i) => (
            <div key={i} className="space-y-3">
              <Skeleton className="h-6 w-48" />
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <Skeleton className="h-40 w-full" />
                <Skeleton className="h-40 w-full" />
              </div>
            </div>
          ))}
        </div>
      ) : !modes || modes.length === 0 ? (
        <Card className="p-12 text-center">
          <GitBranch className="w-6 h-6 text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No interview modes configured.</p>
        </Card>
      ) : (
        <div className="space-y-8">
          {modes.map((mode) => {
            const modeFlows = (flows ?? [])
              .filter((f) => f.mode === mode.value)
              .sort((a, b) => b.version - a.version);
            const live = modeFlows.find((f) => f.status === "published" && f.isDefault);

            return (
              <section key={mode.value} className="space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-3 flex-wrap">
                    <h2 className="text-sm font-semibold text-foreground">{mode.label}</h2>
                    {live ? (
                      <Badge variant="success" className="gap-1.5">
                        <Radio className="w-3 h-3" />
                        Live: {live.name} · v{live.version}
                      </Badge>
                    ) : (
                      <Badge variant="error" className="gap-1.5">
                        <AlertTriangle className="w-3 h-3" />
                        No live flow — sessions in this mode can't start
                      </Badge>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setCreateForMode(mode.value);
                      setCreateOpen(true);
                    }}
                    className="text-xs text-primary hover:underline inline-flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" />
                    New flow for {mode.label}
                  </button>
                </div>

                {modeFlows.length === 0 ? (
                  <Card className="p-6 text-center">
                    <p className="text-xs text-muted-foreground">No flows created for this mode yet.</p>
                  </Card>
                ) : (
                  <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {modeFlows.map((flow) => (
                      <FlowCard
                        key={flow.id}
                        flow={flow}
                        isLive={flow.id === live?.id}
                        onSetLive={() => setDefaultMutation.mutate({ id: flow.id })}
                        settingLive={setDefaultMutation.isPending}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      <CreateFlowModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        defaultMode={createForMode}
        modeHasNoLiveFlow={
          createForMode
            ? !(flows ?? []).some((f) => f.mode === createForMode && f.status === "published" && f.isDefault)
            : true
        }
      />
    </div>
  );
}

function FlowCard({
  flow,
  isLive,
  onSetLive,
  settingLive,
}: {
  flow: InterviewFlow;
  isLive: boolean;
  onSetLive: () => void;
  settingLive: boolean;
}) {
  const canGoLive = flow.status === "published" && !flow.isDefault;

  return (
    <Link href={`/admin/flows/${flow.id}`}>
      <Card
        className={cn(
          "p-5 h-full transition-colors flex flex-col",
          isLive ? "border-success/50 shadow-[0_0_0_1px_rgba(34,197,94,0.15)]" : "hover:border-primary/30"
        )}
      >
        <div className="flex items-start justify-between mb-2 gap-2">
          <Badge variant={flow.status === "published" ? "success" : flow.status === "draft" ? "warning" : "default"}>
            {capitalize(flow.status)} · v{flow.version}
          </Badge>
          {isLive && (
            <Badge variant="success" className="gap-1">
              <Radio className="w-3 h-3" />
              Live
            </Badge>
          )}
        </div>
        <h3 className="font-display font-semibold text-foreground">{flow.name}</h3>
        <p className="text-xs text-muted-foreground mt-1 line-clamp-2 flex-1">{flow.description}</p>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-border gap-2">
          {canGoLive ? (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onSetLive();
              }}
              disabled={settingLive}
              className="text-xs text-primary hover:underline disabled:opacity-50"
            >
              Set as live
            </button>
          ) : (
            <span className="text-xs text-muted-foreground">
              {flow.status === "archived" ? "Archived" : flow.status === "draft" ? "Not published yet" : ""}
            </span>
          )}
          <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
        </div>
      </Card>
    </Link>
  );
}

function CreateFlowModal({
  open,
  onClose,
  defaultMode,
  modeHasNoLiveFlow,
}: {
  open: boolean;
  onClose: () => void;
  defaultMode?: string;
  modeHasNoLiveFlow: boolean;
}) {
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [mode, setMode] = useState(defaultMode ?? "mixed");
  const [makeLive, setMakeLive] = useState(modeHasNoLiveFlow);

  // <Modal> only hides its content when closed (see components/ui) -- this
  // wrapper never unmounts, so useState initializers alone would only ever
  // capture the very first open's props. Re-sync explicitly on every open.
  useEffect(() => {
    if (open) {
      setName("");
      setMode(defaultMode ?? "mixed");
      setMakeLive(modeHasNoLiveFlow);
    }
  }, [open, defaultMode, modeHasNoLiveFlow]);

  const createMutation = useApiMutation<
    { flowId: string },
    { name: string; mode: string; graph_json: object; is_default: boolean }
  >({
    url: "/admin/flows/",
    onSuccess: (data) => {
      toast.success("Flow created");
      queryClient.invalidateQueries({ queryKey: ["/admin/flows/"] });
      setName("");
      onClose();
      router.push(`/admin/flows/${data.flowId}`);
    },
  });

  return (
    <Modal open={open} onClose={onClose} title="New interview flow" description="Publish it, then it goes live for its mode." size="sm">
      <div className="p-6 pt-0 space-y-4">
        <Input label="Flow name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Backend Developer — Technical" />
        <Select
          label="Mode"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          options={[
            { value: "behavioral", label: "Behavioral" },
            { value: "technical", label: "Technical" },
            { value: "mixed", label: "Mixed" },
            { value: "mock_hr_screening", label: "Mock HR Screening" },
          ]}
        />
        <div className="flex items-center justify-between rounded-lg border border-border p-3">
          <div>
            <p className="text-sm text-foreground">Make this the live flow</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Once you publish it, it becomes what every candidate gets in this mode
              {!modeHasNoLiveFlow && " — replacing whatever is live now"}.
            </p>
          </div>
          <Toggle checked={makeLive} onChange={setMakeLive} />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={createMutation.isPending}
            disabled={!name}
            onClick={() =>
              createMutation.mutate({
                name,
                mode,
                is_default: makeLive,
                graph_json: {
                  nodes: [{ id: "start", type: "start", position: { x: 0, y: 0 }, data: {} }],
                  edges: [],
                },
              })
            }
          >
            Create
          </Button>
        </div>
      </div>
    </Modal>
  );
}
