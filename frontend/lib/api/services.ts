import apiClient from "@/lib/api/client";
import type {
  AdminCandidateRow,
  AgentKeyOption,
  AgentPerformance,
  AgentTemplate,
  CandidateKnowledgeEntry,
  CandidateStats,
  CandidateTargetRole,
  FeedbackReport,
  InterviewFlow,
  InterviewSession,
  ModeOption,
  DifficultyOption,
  PlatformOverview,
  SentimentDistributionEntry,
  TokenUsage,
  TranscriptTurn,
  TrendPoint,
} from "@/types";
import type { SuccessResponse, PaginatedResponse } from "@/hooks/use-api";

const unwrap = <T,>(res: { data: SuccessResponse<T> }) => res.data.data;

// ─── Catalog ────────────────────────────────────────────────────────────────

export const catalogService = {
  listModes: () => apiClient.get<SuccessResponse<ModeOption[]>>("/catalog/modes/").then(unwrap),
  listDifficultyLevels: () =>
    apiClient.get<SuccessResponse<DifficultyOption[]>>("/catalog/difficulty-levels/").then(unwrap),
};

// ─── Target Roles (candidate-owned, private) ────────────────────────────────

export const targetRolesService = {
  list: () => apiClient.get<SuccessResponse<CandidateTargetRole[]>>("/target-roles/").then(unwrap),
  get: (id: string) => apiClient.get<SuccessResponse<CandidateTargetRole>>(`/target-roles/${id}/`).then(unwrap),
  create: (payload: { title: string; description?: string }) =>
    apiClient.post<SuccessResponse<{ targetRoleId: string }>>("/target-roles/", payload).then(unwrap),
  update: (id: string, payload: { title?: string; description?: string; is_active?: boolean }) =>
    apiClient.patch<SuccessResponse<object>>(`/target-roles/${id}/`, payload).then(unwrap),
  remove: (id: string) => apiClient.delete<SuccessResponse<object>>(`/target-roles/${id}/`).then(unwrap),
  addField: (id: string, payload: { field_title: string; field_description: string }) =>
    apiClient.post<SuccessResponse<{ fieldId: string }>>(`/target-roles/${id}/fields/`, payload).then(unwrap),
  updateField: (id: string, fieldId: string, payload: { field_title?: string; field_description?: string }) =>
    apiClient.patch<SuccessResponse<object>>(`/target-roles/${id}/fields/${fieldId}/`, payload).then(unwrap),
  removeField: (id: string, fieldId: string) =>
    apiClient.delete<SuccessResponse<object>>(`/target-roles/${id}/fields/${fieldId}/`).then(unwrap),
  analyze: (id: string) =>
    apiClient.post<SuccessResponse<{ status: string }>>(`/target-roles/${id}/analyze/`).then(unwrap),
  listKnowledge: (id: string) =>
    apiClient.get<SuccessResponse<CandidateKnowledgeEntry[]>>(`/target-roles/${id}/knowledge/`).then(unwrap),
};

// ─── Interviews ─────────────────────────────────────────────────────────────

export interface CreateSessionPayload {
  target_role_id?: string;
  flow_id?: string;
  mode: string;
  difficulty: string;
  live_coaching_enabled: boolean;
  recording_consent: boolean;
}
const unwrapData = <T,>(res: any) => res?.data?.data ?? res?.data ?? res;
export const interviewService = {
  createSession: (payload: CreateSessionPayload) =>
  apiClient
    .post("/interviews/sessions/", payload)
    .then(unwrapData),
  getSession: (sessionId: string) =>
    apiClient.get<SuccessResponse<InterviewSession>>(`/interviews/sessions/${sessionId}/`).then(unwrap),
  listSessions: (params: { page: number; limit: number; status?: string }) =>
    apiClient
      .get<PaginatedResponse<InterviewSession>>("/interviews/sessions/", { params })
      .then((res) => res.data),
  getTranscript: (sessionId: string) =>
    apiClient
      .get<SuccessResponse<TranscriptTurn[]>>(`/interviews/sessions/${sessionId}/transcript/`)
      .then(unwrap),
  pauseSession: (sessionId: string) =>
    apiClient.post<SuccessResponse<object>>(`/interviews/sessions/${sessionId}/pause/`).then(unwrap),
  resumeSession: (sessionId: string) =>
    apiClient.post<SuccessResponse<object>>(`/interviews/sessions/${sessionId}/resume/`).then(unwrap),
  endSession: (sessionId: string) =>
    apiClient.post<SuccessResponse<object>>(`/interviews/sessions/${sessionId}/end/`).then(unwrap),
  getReport: (sessionId: string) =>
    apiClient.get<SuccessResponse<FeedbackReport>>(`/interviews/sessions/${sessionId}/report/`).then(unwrap),
  submitRating: (sessionId: string, score: number, comment?: string) =>
    apiClient
      .post<SuccessResponse<object>>(`/interviews/sessions/${sessionId}/rating/`, { score, comment })
      .then(unwrap),
  getMyStats: () => apiClient.get<SuccessResponse<CandidateStats>>("/interviews/me/stats/").then(unwrap),
};

// ─── LiveKit ────────────────────────────────────────────────────────────────

export const livekitService = {
  getJoinToken: (sessionId: string) =>
    apiClient
      .post<SuccessResponse<{ livekitUrl: string; token: string; roomName: string }>>(
        `/livekit/sessions/${sessionId}/token/`
      )
      .then(unwrap),
};

// ─── Admin: Users ───────────────────────────────────────────────────────────

export const adminUsersService = {
  list: (params: { page: number; limit: number; search?: string }) =>
    apiClient
      .get<PaginatedResponse<AdminCandidateRow>>("/admin/users/", { params })
      .then((res) => res.data),
  get: (id: string) => apiClient.get<SuccessResponse<AdminCandidateRow>>(`/admin/users/${id}/`).then(unwrap),
  getSessions: (id: string) =>
    apiClient
      .get<SuccessResponse<{ id: string; status: string; mode: string; difficulty: string; targetRoleId: string | null; targetRoleTitle: string | null; overallScore: number | null; createdAt: string }[]>>(
        `/admin/users/${id}/sessions/`
      )
      .then(unwrap),
  getTargetRoles: (id: string) =>
    apiClient.get<SuccessResponse<CandidateTargetRole[]>>(`/admin/users/${id}/target-roles/`).then(unwrap),
  getTargetRoleDetail: (id: string, targetRoleId: string) =>
    apiClient
      .get<SuccessResponse<CandidateTargetRole>>(`/admin/users/${id}/target-roles/${targetRoleId}/`)
      .then(unwrap),
  getTargetRoleKnowledge: (id: string, targetRoleId: string) =>
    apiClient
      .get<SuccessResponse<CandidateKnowledgeEntry[]>>(`/admin/users/${id}/target-roles/${targetRoleId}/knowledge/`)
      .then(unwrap),
  suspend: (id: string, reason?: string) =>
    apiClient.post<SuccessResponse<object>>(`/admin/users/${id}/suspend/`, { reason }).then(unwrap),
  activate: (id: string) =>
    apiClient.post<SuccessResponse<object>>(`/admin/users/${id}/activate/`).then(unwrap),
  remove: (id: string) => apiClient.delete<SuccessResponse<object>>(`/admin/users/${id}/`).then(unwrap),
};

// ─── Admin: Agents ──────────────────────────────────────────────────────────

export const adminAgentsService = {
  list: (key?: string) =>
    apiClient
      .get<SuccessResponse<AgentTemplate[]>>("/admin/agents/", { params: key ? { key } : {} })
      .then(unwrap),
  // Real, backend-validated list of selectable agents for the flow
  // builder's node editor dropdown — not free text.
  listKeys: () => apiClient.get<SuccessResponse<AgentKeyOption[]>>("/admin/agents/keys/").then(unwrap),
  get: (id: string) => apiClient.get<SuccessResponse<AgentTemplate>>(`/admin/agents/${id}/`).then(unwrap),
  update: (id: string, payload: Partial<AgentTemplate>) =>
    apiClient.patch<SuccessResponse<object>>(`/admin/agents/${id}/`, payload).then(unwrap),
  clone: (id: string) =>
    apiClient.post<SuccessResponse<{ agentId: string }>>(`/admin/agents/${id}/clone/`).then(unwrap),
  publish: (id: string) =>
    apiClient.post<SuccessResponse<object>>(`/admin/agents/${id}/publish/`).then(unwrap),
  archive: (id: string) =>
    apiClient.post<SuccessResponse<object>>(`/admin/agents/${id}/archive/`).then(unwrap),
  test: (id: string, sampleInput: Record<string, unknown>) =>
    apiClient
      .post<SuccessResponse<{ output: Record<string, unknown>; latencyMs: number; modelName: string }>>(
        `/admin/agents/${id}/test/`,
        sampleInput
      )
      .then(unwrap),
};

// ─── Admin: Flows ───────────────────────────────────────────────────────────

export const adminFlowsService = {
  list: (status?: string) =>
    apiClient
      .get<SuccessResponse<InterviewFlow[]>>("/admin/flows/", { params: status ? { status } : {} })
      .then(unwrap),
  get: (id: string) => apiClient.get<SuccessResponse<InterviewFlow>>(`/admin/flows/${id}/`).then(unwrap),
  create: (payload: Partial<InterviewFlow>) =>
    apiClient.post<SuccessResponse<{ flowId: string }>>("/admin/flows/", payload).then(unwrap),
  update: (id: string, payload: Partial<InterviewFlow>) =>
    apiClient.patch<SuccessResponse<object>>(`/admin/flows/${id}/`, payload).then(unwrap),
  clone: (id: string) =>
    apiClient.post<SuccessResponse<{ flowId: string }>>(`/admin/flows/${id}/clone/`).then(unwrap),
  publish: (id: string) =>
    apiClient.post<SuccessResponse<object>>(`/admin/flows/${id}/publish/`).then(unwrap),
  // Promotes an already-published flow to be THE live one for its mode —
  // the only way to change which flow is live without cloning+republishing.
  setDefault: (id: string) =>
    apiClient.post<SuccessResponse<object>>(`/admin/flows/${id}/set-default/`).then(unwrap),
  archive: (id: string) =>
    apiClient.post<SuccessResponse<object>>(`/admin/flows/${id}/archive/`).then(unwrap),
  remove: (id: string) => apiClient.delete<SuccessResponse<object>>(`/admin/flows/${id}/`).then(unwrap),
};

// ─── Admin: Analytics ───────────────────────────────────────────────────────

export const adminAnalyticsService = {
  overview: () => apiClient.get<SuccessResponse<PlatformOverview>>("/admin/analytics/overview/").then(unwrap),
  trend: (days = 30) =>
    apiClient.get<SuccessResponse<TrendPoint[]>>("/admin/analytics/trend/", { params: { days } }).then(unwrap),
  agentPerformance: () =>
    apiClient.get<SuccessResponse<AgentPerformance[]>>("/admin/analytics/agent-performance/").then(unwrap),
  tokenUsage: (days = 30) =>
    apiClient.get<SuccessResponse<TokenUsage>>("/admin/analytics/token-usage/", { params: { days } }).then(unwrap),
  sentimentDistribution: (days = 30) =>
    apiClient
      .get<SuccessResponse<SentimentDistributionEntry[]>>("/admin/analytics/sentiment-distribution/", { params: { days } })
      .then(unwrap),
};

// ─── Admin: Monitoring ──────────────────────────────────────────────────────

export const adminMonitoringService = {
  liveSessions: () =>
    apiClient
      .get<SuccessResponse<{ id: string; status: string; candidateName: string; targetRoleTitle: string | null }[]>>(
        "/admin/monitoring/live-sessions/"
      )
      .then(unwrap),
  health: () =>
    apiClient
      .get<SuccessResponse<{ overall: string; services: Record<string, { status: string }> }>>(
        "/admin/monitoring/health/"
      )
      .then(unwrap),
  errorLogs: () =>
    apiClient
      .get<SuccessResponse<{ id: string; agentKey: string; errorMessage: string; timestamp: string }[]>>(
        "/admin/monitoring/error-logs/"
      )
      .then(unwrap),
};
