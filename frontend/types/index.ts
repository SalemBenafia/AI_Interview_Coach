// ─── Catalog ────────────────────────────────────────────────────────────────

export type InterviewMode = "behavioral" | "technical" | "mixed" | "mock_hr_screening";
export type DifficultyLevel = "junior" | "mid" | "senior";
export type SupportedLanguage = "en" | "fr" | "ar";

export interface ModeOption {
  value: InterviewMode;
  label: string;
  description: string;
}

export interface DifficultyOption {
  value: DifficultyLevel;
  label: string;
  description: string;
}

// ─── Target Roles (candidate-owned, private) ──────────────────────────────

export type TargetRoleStatus = "draft" | "analyzing" | "ready" | "failed";

export interface CandidateTargetRoleField {
  id: string;
  fieldTitle: string;
  fieldDescription: string;
  sortOrder: number;
}

export interface CandidateTargetRole {
  id: string;
  title: string;
  description: string | null;
  status: TargetRoleStatus;
  isActive: boolean;
  createdAt: string;
  updatedAt?: string;
  fields?: CandidateTargetRoleField[];
}

export interface CandidateKnowledgeEntry {
  id: string;
  category: string;
  topic: string;
  summary: string;
  timesCovered: number;
}

// ─── Interview Sessions ────────────────────────────────────────────────────

export type SessionStatus =
  | "scheduled" | "connecting" | "active" | "paused"
  | "completed" | "abandoned" | "failed";

export interface InterviewSession {
  id: string;
  status: SessionStatus;
  mode: InterviewMode;
  difficulty: DifficultyLevel;
  targetRoleId: string | null;
  targetRoleTitle: string | null;
  flowId: string | null;
  livekitRoomName: string | null;
  currentStage: string | null;
  currentQuestion: string | null;
  questionsAsked: number;
  startedAt: string | null;
  endedAt: string | null;
  endedReason: string | null;
  durationSeconds: number | null;
  overallScore: number | null;
  communicationScore: number | null;
  technicalScore: number | null;
  behavioralScore: number | null;
  confidenceScore: number | null;
  createdAt: string;
}

export interface TranscriptTurn {
  turnNumber: number;
  speaker: "ai" | "candidate";
  text: string;
  isFollowup: boolean;
  timestamp: string;
  sentiment: string | null;
  sentimentScore: number | null;
}

export interface FeedbackReport {
  summary: string;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  exampleBetterAnswers: { question: string; your_answer: string; better_answer: string }[];
  recommendedPractice: string[];
  coachingStyle: string | null;
  pdfUrl: string | null;
  generatedAt: string;
  sentimentDistribution: Record<string, number> | null;
  scores: {
    overall: number | null;
    communication: number | null;
    technical: number | null;
    behavioral: number | null;
    confidence: number | null;
    starMethod: number | null;
  };
}

export interface CandidateStats {
  totalCompletedInterviews: number;
  scoreTrend: { sessionId: string; date: string; overallScore: number | null }[];
  averageScoresByDimension: Record<string, number | null>;
  weakestDimension: string | null;
  recommendedPractice: string | null;
}

// ─── AI Studio: Agents ─────────────────────────────────────────────────────

export type AgentKey = "interviewer" | "evaluator" | "router" | "feedback" | "coach";
export type AgentTemplateStatus = "draft" | "active" | "archived";

export interface AgentKeyOption {
  key: AgentKey;
  label: string;
  hasActiveTemplate: boolean;
  activeTemplateName: string | null;
}

export interface AgentTemplate {
  id: string;
  key: AgentKey;
  name: string;
  description: string | null;
  version: number;
  status: AgentTemplateStatus;
  parentId: string | null;
  modelProvider: string;
  modelName: string;
  temperature: number;
  maxTokens: number;
  systemPrompt: string;
  rubric: { key: string; label: string; weight: number }[];
  decisionRules: { condition: string; action: string }[];
  coachingStyle: string | null;
  publishedAt: string | null;
  createdAt: string;
}

// ─── AI Studio: Flows ───────────────────────────────────────────────────────

export type FlowStatus = "draft" | "published" | "archived";
export type FlowNodeType = "start" | "question" | "evaluation" | "router" | "coaching" | "end";
export type RouterAction = "ask_followup" | "next_question" | "increase_difficulty" | "coaching" | "end";

export interface FlowNodeData {
  agent?: AgentKey;
  [key: string]: unknown;
}

export interface FlowNode {
  id: string;
  type: FlowNodeType;
  position: { x: number; y: number };
  data: FlowNodeData;
}

export interface FlowEdgeData {
  action?: RouterAction;
  [key: string]: unknown;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  data?: FlowEdgeData;
}

export interface InterviewFlow {
  id: string;
  name: string;
  description: string | null;
  mode: InterviewMode;
  defaultDifficulty: DifficultyLevel;
  status: FlowStatus;
  version: number;
  parentId: string | null;
  isDefault: boolean;
  graphJson: { nodes: FlowNode[]; edges: FlowEdge[] };
  publishedAt: string | null;
  createdAt: string;
}

// ─── Admin: Users ───────────────────────────────────────────────────────────

export interface AdminCandidateRow {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  isActive: boolean;
  preferredLanguage: string;
  lastLoginAt: string | null;
  createdAt: string;
}

// ─── Admin: Analytics ────────────────────────────────────────────────────────

export interface PlatformOverview {
  totalUsers: number;
  dau: number;
  mau: number;
  interviewsLast30Days: number;
  completedInterviewsLast30Days: number;
  completionRate: number | null;
  avgOverallScore: number | null;
  avgAiLatencyMs: number | null;
  avgFeedbackRating: number | null;
}

export interface TrendPoint {
  date: string;
  totalInterviews: number;
  completedInterviews: number;
  activeUsers: number;
  newUsers: number;
  avgOverallScore: number | null;
  avgAiLatencyMs: number | null;
  completionRate: number | null;
}

export interface AgentPerformance {
  agentKey: string;
  calls: number;
  avgLatencyMs: number | null;
  successRate: number | null;
}

export interface TokenUsageByAgent {
  agentKey: string;
  modelName: string;
  totalTokens: number;
  calls: number;
}

export interface TokenUsageDaily {
  date: string;
  totalTokens: number;
}

export interface TokenUsage {
  byAgent: TokenUsageByAgent[];
  dailyTotals: TokenUsageDaily[];
}

export interface SentimentDistributionEntry {
  label: string;
  count: number;
  percentage: number;
}

// ─── Notifications ──────────────────────────────────────────────────────────

export interface NotificationItem {
  id: string;
  channel: string;
  subject: string | null;
  body: string;
  status: string;
  isRead: boolean;
  createdAt: string;
}
