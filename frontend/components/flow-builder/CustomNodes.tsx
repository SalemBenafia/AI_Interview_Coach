"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  Flag, MessageSquareText, ClipboardCheck, GitMerge, Lightbulb, CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils/utils";

interface FlowNodeData {
  label?: string;
  agent?: string;
  [key: string]: unknown;
}

const NODE_STYLES: Record<
  string,
  { icon: typeof Flag; accent: string; bg: string; border: string }
> = {
  start: { icon: Flag, accent: "text-foreground", bg: "bg-card", border: "border-white/15" },
  question: { icon: MessageSquareText, accent: "text-primary", bg: "bg-primary/5", border: "border-primary/30" },
  evaluation: { icon: ClipboardCheck, accent: "text-accent", bg: "bg-accent/5", border: "border-accent/30" },
  router: { icon: GitMerge, accent: "text-warning", bg: "bg-warning/5", border: "border-warning/30" },
  coaching: { icon: Lightbulb, accent: "text-accent", bg: "bg-accent/5", border: "border-accent/30" },
  end: { icon: CheckCircle2, accent: "text-success", bg: "bg-success/5", border: "border-success/30" },
};

function BaseNode({ type, data, selected }: { type: string; data: FlowNodeData; selected?: boolean }) {
  const style = NODE_STYLES[type] ?? NODE_STYLES.question;
  const Icon = style.icon;

  return (
    <div
      className={cn(
        "min-w-44 rounded-lg border-2 px-3.5 py-2.5 shadow-card backdrop-blur-sm transition-shadow",
        style.bg,
        selected ? "border-primary shadow-neon-sm" : style.border
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-primary !w-2 !h-2 !border-none" />
      <div className="flex items-center gap-2">
        <Icon className={cn("w-3.5 h-3.5 flex-shrink-0", style.accent)} />
        <span className="text-xs font-semibold text-foreground capitalize">{type}</span>
      </div>
      {data?.agent && (
        <p className="text-2xs text-muted-foreground mt-1 truncate">agent: {data.agent}</p>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-primary !w-2 !h-2 !border-none" />
    </div>
  );
}

export function StartNode(props: NodeProps) {
  return <BaseNode type="start" data={props.data as FlowNodeData} selected={props.selected} />;
}
export function QuestionNode(props: NodeProps) {
  return <BaseNode type="question" data={props.data as FlowNodeData} selected={props.selected} />;
}
export function EvaluationNode(props: NodeProps) {
  return <BaseNode type="evaluation" data={props.data as FlowNodeData} selected={props.selected} />;
}
export function RouterNode(props: NodeProps) {
  return <BaseNode type="router" data={props.data as FlowNodeData} selected={props.selected} />;
}
export function CoachingNode(props: NodeProps) {
  return <BaseNode type="coaching" data={props.data as FlowNodeData} selected={props.selected} />;
}
export function EndNode(props: NodeProps) {
  return <BaseNode type="end" data={props.data as FlowNodeData} selected={props.selected} />;
}

export const nodeTypes = {
  start: StartNode,
  question: QuestionNode,
  evaluation: EvaluationNode,
  router: RouterNode,
  coaching: CoachingNode,
  end: EndNode,
};

// "start" is intentionally excluded here: a flow may have only one, and the
// flow editor page seeds it automatically on a new draft — see flowJson
// default in the create-flow modal (frontend/app/admin/flows/page.tsx).
export const NODE_PALETTE: { type: string; label: string }[] = [
  { type: "question", label: "Question" },
  { type: "evaluation", label: "Evaluation" },
  { type: "router", label: "Router" },
  { type: "coaching", label: "Coaching" },
  { type: "end", label: "End" },
];
