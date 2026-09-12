"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  ReactFlow, Background, Controls, MiniMap, addEdge, useNodesState, useEdgesState,
  BackgroundVariant, type Connection, type Edge, type Node, type OnConnect,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ArrowLeft, Copy, Rocket, Archive, Save, Plus, Trash2, AlertCircle, Radio } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api";
import { adminFlowsService } from "@/lib/api/services";
import { nodeTypes, NODE_PALETTE } from "@/components/flow-builder/CustomNodes";
import { Button, Badge, Select, Skeleton, Toggle, Modal } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";
import { capitalize } from "@/lib/utils/utils";
import type { AgentKey, AgentKeyOption, InterviewFlow, RouterAction } from "@/types";

let nodeIdCounter = 1000;

// Which agents a node of a given type may use — mirrors backend
// app/modules/agents/flow_contracts.py's NODE_TYPE_AGENT_KEYS. Kept as a
// small, duplicated constant here (not fetched) since it's a structural
// contract, not data — the backend independently enforces it at publish
// time regardless of what this dropdown offers.
const NODE_TYPE_AGENT_KEYS: Record<string, AgentKey[]> = {
  question: ["interviewer"],
  evaluation: ["evaluator"],
  router: ["router"],
  coaching: ["coach"],
};

const DEFAULT_AGENT_FOR_TYPE: Record<string, AgentKey | undefined> = {
  question: "interviewer",
  evaluation: "evaluator",
  router: "router",
  coaching: "coach",
};

// Mirrors backend app/modules/agents/flow_contracts.py's ROUTER_ACTIONS /
// app/modules/agents/router_agent.py's _VALID_ACTIONS.
const ROUTER_ACTIONS: { value: RouterAction; label: string }[] = [
  { value: "ask_followup", label: "Ask follow-up" },
  { value: "next_question", label: "Next question" },
  { value: "increase_difficulty", label: "Increase difficulty" },
  { value: "coaching", label: "Coaching" },
  { value: "end", label: "End interview" },
];

export default function FlowEditorPage() {
  const params = useParams<{ flowId: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const flowQueryKey = [`/admin/flows/${params.flowId}/`];
  const invalidateFlow = () => {
    queryClient.invalidateQueries({ queryKey: flowQueryKey });
    queryClient.invalidateQueries({ queryKey: ["/admin/flows/"] });
  };

  const { data: flow, isLoading } = useApiQuery<InterviewFlow>({ url: `/admin/flows/${params.flowId}/` });
  const { data: agentOptions } = useApiQuery<AgentKeyOption[]>({ url: "/admin/agents/keys/" });

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [settingLive, setSettingLive] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // Draft-only: whether this flow should become the live one for its mode
  // once published. Published flows can't change this here — see
  // handleSetLive, the only way to promote an already-published flow.
  const [makeLiveOnPublish, setMakeLiveOnPublish] = useState(false);

  useEffect(() => {
    if (flow) {
      setNodes(
        flow.graphJson.nodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          data: n.data,
        }))
      );
      setEdges(
        flow.graphJson.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          data: e.data ?? {},
          label: e.data?.action,
          animated: true,
        }))
      );
      setMakeLiveOnPublish(flow.isDefault);
    }
  }, [flow, setNodes, setEdges]);

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge({ ...connection, data: {}, animated: true }, eds)),
    [setEdges]
  );

  const addNode = (type: string) => {
    nodeIdCounter += 1;
    const id = `${type}-${nodeIdCounter}`;
    setNodes((nds) => [
      ...nds,
      {
        id,
        type,
        position: { x: 250 + Math.random() * 100, y: 150 + nds.length * 40 },
        data: { agent: DEFAULT_AGENT_FOR_TYPE[type] },
      },
    ]);
  };

  const deleteSelectedNode = () => {
    if (!selectedNodeId) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId));
    setSelectedNodeId(null);
  };

  const deleteSelectedEdge = () => {
    if (!selectedEdgeId) return;
    setEdges((eds) => eds.filter((e) => e.id !== selectedEdgeId));
    setSelectedEdgeId(null);
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);
  const selectedEdgeSourceNode = selectedEdge ? nodes.find((n) => n.id === selectedEdge.source) : undefined;
  const isEditable = flow?.status === "draft";

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminFlowsService.update(params.flowId, {
        // NOTE: backend Pydantic schemas are snake_case (FastAPI convention),
        // so this payload intentionally does not match the camelCase
        // InterviewFlow TS type used elsewhere on this page.
        graph_json: {
          nodes: nodes.map((n) => ({ id: n.id, type: n.type ?? "question", position: n.position, data: n.data as never })),
          edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target, data: (e.data as never) ?? {} })),
        },
        is_default: makeLiveOnPublish,
      } as Partial<InterviewFlow>);
      toast.success("Flow saved");
      invalidateFlow();
    } catch {
      toast.error("Couldn't save the flow");
    } finally {
      setSaving(false);
    }
  };

  const handleSetLive = async () => {
    setSettingLive(true);
    try {
      await adminFlowsService.setDefault(params.flowId);
      toast.success("This is now the live flow for its mode");
      invalidateFlow();
    } catch {
      toast.error("Couldn't set this flow as live");
    } finally {
      setSettingLive(false);
    }
  };

  const handleClone = async () => {
    const result = await adminFlowsService.clone(params.flowId);
    toast.success("Cloned into a new draft");
    queryClient.invalidateQueries({ queryKey: ["/admin/flows/"] });
    router.push(`/admin/flows/${result.flowId}`);
  };

  const handlePublish = async () => {
    await handleSave();
    try {
      await adminFlowsService.publish(params.flowId);
      toast.success("Flow published");
      invalidateFlow();
    } catch (err: any) {
      // Backend raises HTTPException(422, detail={"code","message","errors"})
      // on a structurally invalid flow — FastAPI wraps that as
      // response.data.detail, not response.data.error (see
      // app/modules/admin/flows/router.py's publish_flow).
      const errors: string[] | undefined = err?.response?.data?.detail?.errors;
      toast.error(
        "Flow failed validation",
        errors && errors.length ? errors.join(" • ") : "Fix the flow structure before publishing."
      );
    }
  };

  const handleArchive = async () => {
    await adminFlowsService.archive(params.flowId);
    toast.success("Flow archived");
    queryClient.invalidateQueries({ queryKey: ["/admin/flows/"] });
    router.push("/admin/flows");
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await adminFlowsService.remove(params.flowId);
      toast.success("Draft deleted");
      queryClient.invalidateQueries({ queryKey: ["/admin/flows/"] });
      router.push("/admin/flows");
    } catch {
      toast.error("Couldn't delete this flow");
      setDeleting(false);
    }
  };

  if (isLoading || !flow) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }

  const allowedAgents = selectedNode ? NODE_TYPE_AGENT_KEYS[selectedNode.type ?? ""] ?? [] : [];
  const agentSelectOptions = (agentOptions ?? [])
    .filter((a) => allowedAgents.includes(a.key))
    .map((a) => ({
      value: a.key,
      label: a.activeTemplateName ? `${a.label} (${a.activeTemplateName})` : a.label,
    }));

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] -m-4 sm:-m-6 animate-fade-in">
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-3 px-4 sm:px-6 py-3 border-b border-border bg-card/40">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push("/admin/flows")}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="font-display font-semibold text-foreground">{flow.name}</h1>
              <Badge variant={flow.status === "published" ? "success" : "warning"}>
                {capitalize(flow.status)} · v{flow.version}
              </Badge>
              <Badge variant="default" className="capitalize">
                {flow.mode.replace("_", " ")}
              </Badge>
              {flow.status === "published" && flow.isDefault && (
                <Badge variant="success" className="gap-1">
                  <Radio className="w-3 h-3" />
                  Live for this mode
                </Badge>
              )}
            </div>
            <p className="text-2xs text-muted-foreground mt-0.5">
              {flow.status === "published" && flow.isDefault
                ? "This is the flow every candidate actually gets in this mode right now."
                : flow.status === "published"
                  ? "Published, but NOT live — another flow is currently serving this mode. Use \"Set as live\" to switch."
                  : "Global once published — applies to every candidate and target role interviewing in this mode."}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isEditable && (
            <div className="flex items-center gap-2 pr-2 border-r border-border">
              <Toggle checked={makeLiveOnPublish} onChange={setMakeLiveOnPublish} size="sm" />
              <span className="text-xs text-muted-foreground">Make live on publish</span>
            </div>
          )}
          {flow.status === "published" && !flow.isDefault && (
            <Button variant="outline" size="sm" leftIcon={<Radio className="w-3.5 h-3.5" />} loading={settingLive} onClick={handleSetLive}>
              Set as live
            </Button>
          )}
          <Button variant="outline" size="sm" leftIcon={<Copy className="w-3.5 h-3.5" />} onClick={handleClone}>
            Clone
          </Button>
          {isEditable && (
            <>
              <Button variant="outline" size="sm" leftIcon={<Save className="w-3.5 h-3.5" />} loading={saving} onClick={handleSave}>
                Save
              </Button>
              <Button size="sm" leftIcon={<Rocket className="w-3.5 h-3.5" />} onClick={handlePublish}>
                Publish
              </Button>
            </>
          )}
          {flow.status === "published" && (
            <Button variant="outline" size="sm" leftIcon={<Archive className="w-3.5 h-3.5" />} onClick={handleArchive}>
              Archive
            </Button>
          )}
          {flow.status === "draft" && (
            <Button
              variant="danger"
              size="sm"
              leftIcon={<Trash2 className="w-3.5 h-3.5" />}
              onClick={() => setDeleteConfirmOpen(true)}
            >
              Delete
            </Button>
          )}
        </div>
      </div>

      <Modal
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        title="Delete this draft flow?"
        description="This permanently removes the flow. This cannot be undone."
        size="sm"
      >
        <div className="p-6 pt-0 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setDeleteConfirmOpen(false)}>
            Cancel
          </Button>
          <Button variant="danger" loading={deleting} onClick={handleDelete}>
            Delete
          </Button>
        </div>
      </Modal>

      <div className="flex-1 flex overflow-hidden">
        {/* Node palette */}
        {isEditable && (
          <div className="w-44 border-r border-border bg-card/20 p-3 space-y-1.5 overflow-y-auto scrollbar-thin">
            <p className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground px-1 mb-2">Add node</p>
            {NODE_PALETTE.map((item) => (
              <button
                key={item.type}
                type="button"
                onClick={() => addNode(item.type)}
                className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors text-left"
              >
                <Plus className="w-3 h-3" />
                {item.label}
              </button>
            ))}
            <div className="pt-2 mt-2 border-t border-border flex items-start gap-1.5 px-1">
              <AlertCircle className="w-3 h-3 text-muted-foreground flex-shrink-0 mt-0.5" />
              <p className="text-2xs text-muted-foreground leading-snug">
                Router edges carry an action, not a topic — click an edge from a router node to set it.
              </p>
            </div>
          </div>
        )}

        {/* Canvas */}
        <div className="flex-1 bg-background">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={isEditable ? onNodesChange : undefined}
            onEdgesChange={isEditable ? onEdgesChange : undefined}
            onConnect={isEditable ? onConnect : undefined}
            onNodeClick={(_, node) => {
              setSelectedNodeId(node.id);
              setSelectedEdgeId(null);
            }}
            onEdgeClick={(_, edge) => {
              setSelectedEdgeId(edge.id);
              setSelectedNodeId(null);
            }}
            onPaneClick={() => {
              setSelectedNodeId(null);
              setSelectedEdgeId(null);
            }}
            nodeTypes={nodeTypes}
            nodesDraggable={isEditable}
            nodesConnectable={isEditable}
            fitView
            colorMode="dark"
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="hsl(150 30% 16%)" />
            <Controls />
            <MiniMap nodeColor="hsl(156 100% 50%)" maskColor="hsl(150 24% 4% / 0.8)" />
          </ReactFlow>
        </div>

        {/* Properties panel */}
        {selectedNode && (
          <div className="w-72 border-l border-border bg-card/20 p-4 space-y-4 overflow-y-auto scrollbar-thin">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground capitalize">{selectedNode.type} node</p>
              {isEditable && (
                <button
                  type="button"
                  onClick={deleteSelectedNode}
                  className="text-muted-foreground hover:text-error transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            {allowedAgents.length > 0 ? (
              <Select
                label="Agent"
                disabled={!isEditable}
                value={(selectedNode.data?.agent as string) ?? ""}
                onChange={(e) =>
                  setNodes((nds) =>
                    nds.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, agent: e.target.value } } : n))
                  )
                }
                options={agentSelectOptions}
                placeholder={agentOptions ? "Select an agent…" : "Loading agents…"}
              />
            ) : (
              <p className="text-xs text-muted-foreground">
                {selectedNode.type === "start"
                  ? "Structural marker — no agent needed. It must have exactly one outgoing edge, to a question node."
                  : "Structural marker — no agent needed. This is where router edges with action \"end\" lead."}
              </p>
            )}
          </div>
        )}

        {selectedEdge && (
          <div className="w-72 border-l border-border bg-card/20 p-4 space-y-4 overflow-y-auto scrollbar-thin">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Edge</p>
              {isEditable && (
                <button
                  type="button"
                  onClick={deleteSelectedEdge}
                  className="text-muted-foreground hover:text-error transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            {selectedEdgeSourceNode?.type === "router" ? (
              <Select
                label="Router action"
                disabled={!isEditable}
                value={(selectedEdge.data?.action as string) ?? ""}
                onChange={(e) =>
                  setEdges((eds) =>
                    eds.map((edge) =>
                      edge.id === selectedEdge.id
                        ? { ...edge, data: { ...edge.data, action: e.target.value }, label: e.target.value }
                        : edge
                    )
                  )
                }
                options={ROUTER_ACTIONS}
                placeholder="Select an action…"
              />
            ) : (
              <p className="text-xs text-muted-foreground">
                Only edges leaving a router node carry an action. This edge has no configurable properties.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
