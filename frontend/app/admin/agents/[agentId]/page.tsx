"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Copy, Rocket, Archive, Play, Loader2, Save } from "lucide-react";
import { useApiQuery, useApiMutation } from "@/hooks/use-api";
import { adminAgentsService } from "@/lib/api/services";
import { Card, CardContent, CardHeader, CardTitle, Badge, Input, Textarea, Select, Button, Tabs, Skeleton } from "@/components/ui";
import { useToast } from "@/store/use-ui-store";
import { capitalize } from "@/lib/utils/utils";
import type { AgentTemplate } from "@/types";

export default function AgentDetailPage() {
  const params = useParams<{ agentId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [tab, setTab] = useState("config");
  const [sampleInput, setSampleInput] = useState("{\n  \n}");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  const { data: agent, isLoading } = useApiQuery<AgentTemplate>({ url: `/admin/agents/${params.agentId}/` });

  const [systemPrompt, setSystemPrompt] = useState("");
  const [modelName, setModelName] = useState("");
  const [temperature, setTemperature] = useState("0.7");
  const [coachingStyle, setCoachingStyle] = useState("professional");

  useEffect(() => {
    if (agent) {
      setSystemPrompt(agent.systemPrompt);
      setModelName(agent.modelName);
      setTemperature(String(agent.temperature));
      setCoachingStyle(agent.coachingStyle ?? "professional");
    }
  }, [agent]);

  const isEditable = agent?.status === "draft";

  const updateMutation = useApiMutation<unknown, Partial<AgentTemplate>>({
    url: `/admin/agents/${params.agentId}/`,
    method: "patch",
    onSuccess: () => {
      toast.success("Saved");
      queryClient.invalidateQueries({ queryKey: [`/admin/agents/${params.agentId}/`] });
    },
  });

  const handleClone = async () => {
    const result = await adminAgentsService.clone(params.agentId);
    toast.success("Cloned into a new draft");
    router.push(`/admin/agents/${result.agentId}`);
  };

  const handlePublish = async () => {
    await adminAgentsService.publish(params.agentId);
    toast.success("Published — this version is now live");
    queryClient.invalidateQueries({ queryKey: [`/admin/agents/${params.agentId}/`] });
  };

  const handleArchive = async () => {
    await adminAgentsService.archive(params.agentId);
    toast.success("Archived");
    router.push("/admin/agents");
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const parsed = JSON.parse(sampleInput);
      const result = await adminAgentsService.test(params.agentId, parsed);
      setTestResult(JSON.stringify(result, null, 2));
    } catch (err) {
      setTestResult(`Error: ${err instanceof Error ? err.message : "Invalid input"}`);
    } finally {
      setTesting(false);
    }
  };

  if (isLoading || !agent) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <button
        type="button"
        onClick={() => router.push("/admin/agents")}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to agents
      </button>

      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-display font-bold text-foreground">{agent.name}</h1>
            <Badge variant={agent.status === "active" ? "success" : agent.status === "draft" ? "warning" : "default"}>
              {capitalize(agent.status)} · v{agent.version}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1 capitalize">{agent.key} agent</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<Copy className="w-3.5 h-3.5" />} onClick={handleClone}>
            Clone
          </Button>
          {agent.status === "draft" && (
            <Button size="sm" leftIcon={<Rocket className="w-3.5 h-3.5" />} onClick={handlePublish}>
              Publish
            </Button>
          )}
          {agent.status === "active" && (
            <Button variant="outline" size="sm" leftIcon={<Archive className="w-3.5 h-3.5" />} onClick={handleArchive}>
              Archive
            </Button>
          )}
        </div>
      </div>

      <Tabs
        tabs={[
          { value: "config", label: "Configuration" },
          { value: "test", label: "Test sandbox" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "config" ? (
        <Card>
          <CardHeader>
            <CardTitle>Model & prompt</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {!isEditable && (
              <p className="text-xs text-warning bg-warning-muted border border-warning/20 rounded-lg px-3 py-2">
                This version is {agent.status} and read-only. Clone it to create an editable draft.
              </p>
            )}
            {agent.key !== "router" && agent.modelProvider !== "groq" && (
              <p className="text-xs text-warning bg-warning-muted border border-warning/20 rounded-lg px-3 py-2">
                This template's provider is "{agent.modelProvider}", but only Groq is currently wired up at
                interview runtime — the engine silently substitutes the default Groq model instead of what's
                configured here. Set the provider to "groq" for this template to actually take effect.
              </p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Input label="Model" disabled={!isEditable} value={modelName} onChange={(e) => setModelName(e.target.value)} />
              <Input label="Temperature" disabled={!isEditable} value={temperature} onChange={(e) => setTemperature(e.target.value)} />
            </div>
            <Textarea
              label="System prompt"
              disabled={!isEditable}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="min-h-64 font-mono-coach text-xs"
            />
            {agent.key === "feedback" && (
              <Select
                label="Coaching style"
                disabled={!isEditable}
                value={coachingStyle}
                onChange={(e) => setCoachingStyle(e.target.value)}
                options={[
                  { value: "friendly", label: "Friendly" },
                  { value: "professional", label: "Professional" },
                  { value: "strict", label: "Strict" },
                  { value: "mentor", label: "Mentor" },
                ]}
              />
            )}
            {agent.rubric.length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Rubric weights</label>
                <div className="space-y-1.5">
                  {agent.rubric.map((r) => (
                    <div key={r.key} className="flex items-center justify-between text-sm px-3 py-2 rounded-lg bg-muted">
                      <span className="text-foreground">{r.label}</span>
                      <span className="text-muted-foreground font-mono-coach">{r.weight}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {agent.decisionRules.length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Decision rules</label>
                <div className="space-y-1.5">
                  {agent.decisionRules.map((r, i) => (
                    <div key={i} className="flex items-center justify-between text-sm px-3 py-2 rounded-lg bg-muted font-mono-coach text-xs">
                      <span className="text-accent">{r.condition}</span>
                      <span className="text-primary">→ {r.action}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {isEditable && (
              <div className="flex justify-end">
                <Button
                  leftIcon={<Save className="w-4 h-4" />}
                  loading={updateMutation.isPending}
                  onClick={() =>
                    updateMutation.mutate({
                      system_prompt: systemPrompt,
                      model_name: modelName,
                      temperature: parseFloat(temperature),
                      ...(agent.key === "feedback" ? { coaching_style: coachingStyle } : {}),
                    } as Partial<AgentTemplate>)
                  }
                >
                  Save draft
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Test sandbox</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              Runs a real call against this agent — no interview session or transcript is created.
            </p>
            <Textarea
              label="Sample input (JSON)"
              value={sampleInput}
              onChange={(e) => setSampleInput(e.target.value)}
              className="min-h-32 font-mono-coach text-xs"
            />
            <Button onClick={handleTest} loading={testing} leftIcon={<Play className="w-4 h-4" />}>
              Run test
            </Button>
            {testResult && (
              <pre className="text-xs font-mono-coach bg-muted rounded-lg p-4 overflow-x-auto whitespace-pre-wrap">
                {testResult}
              </pre>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
