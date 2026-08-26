// ═══ 选题 ═══
export interface CurrentUser {
  id: string;
  username: string;
  displayName: string | null;
  role: "admin" | "user";
  isActive: boolean;
}

export interface ManagedUser extends CurrentUser {
  lastLoginAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface UserListResponse {
  items: ManagedUser[];
  total: number;
}

export interface ResearchMessage {
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export interface TopicScores {
  counterintuitive?: number;
  defensibility?: number;
  visual?: number;
  freshness?: number;
}

export interface Topic {
  id: string;
  title: string;
  description: string | null;
  source: "manual" | "ai_brainstorm" | "audience" | "competitor";
  status: "pending" | "stocked" | "used" | "abandoned";
  scoreCounterintuitive: number | null;
  scoreDefensibility: number | null;
  scoreVisual: number | null;
  scoreFreshness: number | null;
  compositeScore: number | null;
  performanceScore: number | null;
  tags: string[];
  needsRecheck: boolean;
  researchData: ResearchMessage[];
  createdAt: string;
  updatedAt: string;
}

export interface BrainstormCandidate {
  title: string;
  description: string;
  tags: string[];
}

// ═══ 风格组件 ═══
export interface PromptComponent {
  id: string;
  category: string;
  name: string;
  description: string | null;
  promptText: string;
  isBuiltin: boolean;
  createdBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface PromptComponentListResponse {
  items: PromptComponent[];
  total: number;
}

export interface StyleTemplate {
  id: string;
  name: string;
  description: string | null;
  styleConfig: Record<string, string>;
  createdAt: string;
  updatedAt: string;
}

export interface StyleTemplateListResponse {
  items: StyleTemplate[];
  total: number;
}

export interface StyleAssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface StyleAssistantResponse {
  reply: string;
  name: string;
  description: string;
  promptText: string;
}

export interface StyleLibraryComponentDraft {
  name: string;
  description: string;
  promptText: string;
}

export interface StyleLibraryDraft {
  name: string;
  description: string;
  components: Record<string, StyleLibraryComponentDraft>;
}

export interface StyleLibraryAssistantResponse extends StyleLibraryDraft {
  reply: string;
}

// ═══ AI 模型配置 ═══
export type AIProviderType =
  | "deepseek"
  | "openrouter"
  | "gemini"
  | "doubao"
  | "anthropic";

export interface AIModelProvider {
  id: string;
  name: string;
  providerType: AIProviderType;
  baseUrl: string;
  timeoutSeconds: number;
  siteUrl: string | null;
  siteName: string | null;
  isActive: boolean;
  apiKeySet: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AIProviderModel {
  id: string;
  providerId: string;
  name: string;
  model: string;
  contentMaxTokens: number;
  jsonMaxTokens: number;
  inputCostPerMillion: string;
  cachedInputCostPerMillion: string;
  outputCostPerMillion: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AIBusinessModelConfig {
  id: string;
  business: string;
  modelId: string;
  createdAt: string;
  updatedAt: string;
}

export interface AIBusinessOption {
  key: string;
  label: string;
}

export interface AIModelSettingsResponse {
  providers: AIModelProvider[];
  models: AIProviderModel[];
  businessConfigs: AIBusinessModelConfig[];
  businessOptions: AIBusinessOption[];
}

export interface AIModelTestResponse {
  ok: boolean;
  latencyMs: number | null;
  reply: string | null;
  message: string | null;
}

// ═══ AI 调用记录 ═══
export type AICallStatus =
  | "pending"
  | "succeeded"
  | "failed"
  | "timeout"
  | "cancelled";

export interface AICallRecord {
  id: string;
  provider: string;
  model: string;
  business:
    | "narrative_generation"
    | "code_generation"
    | "code_repair"
    | "topic_brainstorm"
    | "topic_research"
    | "style_assistant"
    | "unknown";
  requestType: "chat" | "stream";
  status: AICallStatus;
  promptTokens: number | null;
  completionTokens: number | null;
  totalTokens: number | null;
  cachedTokens: number | null;
  reasoningTokens: number | null;
  totalCost: string | null;
  currency: string;
  durationMs: number | null;
  errorType: string | null;
  outputPreview: string | null;
  startedAt: string;
  completedAt: string | null;
}

export interface AICallRecordDetail extends AICallRecord {
  input: Record<string, unknown>;
  output: string | null;
  usage: Record<string, unknown> | null;
  inputCost: string | null;
  outputCost: string | null;
  errorMessage: string | null;
  createdAt: string;
}

export interface AICallRecordListResponse {
  items: AICallRecord[];
  total: number;
  summary: {
    calls: number;
    succeeded: number;
    failed: number;
    totalTokens: number;
    totalCost: string;
    averageDurationMs: number;
  };
}

// ═══ 视频项目 ═══
export type ProjectStatus =
  | "draft"
  | "narrative_generating"
  | "narrative_review"
  | "narrative_failed"
  | "code_generating"
  | "code_failed"
  | "code_review"
  | "video_generating"
  | "video_failed"
  | "video_review"
  | "published"
  | "abandoned";

export interface NarrativeScene {
  sceneIndex: number;
  narration: string;
  description: string;
  beats: NarrativeBeat[];
  estimatedDurationSeconds: number | null;
  audioKey: string | null;
  durationSeconds: number | null;
  ttsStatus: "ready" | "failed" | "skipped" | "pending" | null;
  audioPresignedUrl: string | null;
  wordTimestamps: WordTimestamp[];
  alignmentCoverage: number | null;
  contentSchemaVersion: number;
}

export interface NarrativeBeat {
  beatIndex: number;
  cueText: string;
  visualAction: string;
  emphasis: string | null;
  transition: "continue" | "transform" | "reveal" | "replace" | "exit";
  fallbackWeight: number;
  cueStartChar: number | null;
  cueEndChar: number | null;
  speechStartSeconds: number | null;
  speechEndSeconds: number | null;
  animationStartSeconds: number | null;
  animationEndSeconds: number | null;
  alignmentStatus: "pending" | "aligned" | "interpolated" | "failed";
}

export interface WordTimestamp {
  word: string;
  startTime: number;
  endTime: number;
  confidence: number | null;
}

export interface NarrativeVersion {
  id: string;
  versionNumber: number;
  scenes: NarrativeScene[];
  factChecks: FactCheckItem[];
  aiModel: string | null;
  rejectionContext: RejectionContext | null;
  promptSnapshot: Record<string, unknown> | null;
  createdAt: string;
}

export interface VideoProject {
  id: string;
  topicId: string;
  topicTitle: string;
  status: ProjectStatus;
  renderEngine: "manim" | "remotion";
  ttsVoice: string;
  ttsEngine: string;
  ttsSpeed: 0.9 | 1.0 | 1.1 | 1.2;
  aspectRatio: "landscape" | "portrait";
  executionMode?: "prompt" | "agent" | null;
  currentCodeVersion: CodeVersion | null;
  currentVideoAsset: VideoAsset | null;
  retryCount: number;
  styleConfig: Record<string, string>;
  createdAt: string;
  updatedAt: string;
}

// ═══ 镜头 ═══
export interface Scene {
  sceneIndex: number;
  narration: string;
  description: string;
  code: string;
  beats: NarrativeBeat[];
  estimatedDurationSeconds: number;
  durationSeconds: number | null;
}

// ═══ 事实核查条目 ═══
export interface FactCheckItem {
  claimText: string;
  sceneIndex: number;
  sourceUrl: string | null;
  sourceDescription: string;
  confidence: "high" | "medium" | "low";
  isHypothesis: boolean;
  assumptions: string | null;
  controversy: string | null;
  reviewerVerdict: "approved" | "rejected" | "needs_revision" | null;
  reviewerNote: string | null;
}

// ═══ 代码版本 ═══
export interface CodeVersion {
  id: string;
  projectId: string;
  versionNumber: number;
  scenes: Scene[];
  factChecks: FactCheckItem[];
  renderEngine: "manim" | "remotion";
  aiModel: string | null;
  rejectionContext: RejectionContext | null;
  promptSnapshot: Record<string, unknown> | null;
  createdAt: string;
}

// ═══ 视频产物 ═══
export interface VideoAsset {
  id: string;
  projectId: string;
  codeVersionId: string;
  videoFileKey: string | null;
  durationSeconds: number | null;
  resolution: string | null;
  renderLog: string | null;
  errorMessage: string | null;
  status: "rendering" | "ready" | "failed";
  createdAt: string;
}

// ═══ 审核请求 ═══
export interface ReviewRequest {
  gate: "narrative" | "code" | "video";
  verdict: "approved" | "rejected" | "abandoned" | "retry";
  rejectionType?: string;
  rejectionDetail?: string;
  targetStage?: "narrative" | "code";
  sceneAnnotations?: SceneReviewAnnotation[];
  factCheckVerdicts?: Array<{
    index: number;
    verdict: "approved" | "rejected" | "needs_revision";
    note: string;
  }>;
  editedScenes?: Array<{
    sceneIndex: number;
    narration: string;
    description: string;
    beats: NarrativeBeat[];
    estimatedDurationSeconds?: number | null;
  }>;
  editedCodeScenes?: Array<{
    sceneIndex: number;
    code: string;
  }>;
}

export interface CodeRepair {
  sceneIndex: number;
  code: string;
  explanation: string;
}

export interface CodeRepairResponse {
  repairs: CodeRepair[];
}

// ═══ 驳回上下文 ═══
export interface SceneReviewAnnotation {
  sceneIndex: number;
  narrativeIssue?: string | null;
  codeIssue?: string | null;
}

export interface RejectionContext {
  gate?: "narrative" | "code" | "video";
  verdict?: string;
  rejectionType?: string | null;
  rejectionDetail?: string | null;
  rejection_type?: string | null;
  rejection_detail?: string | null;
  targetStage?: string | null;
  target_stage?: string | null;
  rejectedAt?: string;
  sceneAnnotations?: SceneReviewAnnotation[];
  scene_annotations?: Array<{
    scene_index?: number;
    sceneIndex?: number;
    narrative_issue?: string | null;
    narrativeIssue?: string | null;
    code_issue?: string | null;
    codeIssue?: string | null;
  }>;
}

// ═══ 异步任务 ═══
export interface WorkerTask {
  id: string;
  projectId: string;
  taskType: "generate_narrative" | "generate_code" | "render_video";
  engine: string;
  status: "pending" | "processing" | "completed" | "failed";
  retryCount: number;
  maxRetries: number;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

// ═══ 项目事件 ═══
export interface ProjectEvent {
  id: number;
  projectId: string;
  eventType: string;
  fromStatus: string | null;
  toStatus: string | null;
  actor: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

// ═══ 表现数据 ═══
export interface PerformanceRecord {
  id: string;
  projectId: string;
  platform: string;
  views: number;
  completionRate: number;
  likes: number;
  favorites: number;
  commentTags: string[];
  commentSummary: string | null;
  recordedAt: string;
}

// ═══ TTS 再生成响应 ═══
export interface RegenerateTtsResponse {
  audioKey: string | null;
  durationSeconds: number | null;
  ttsStatus: string;
  presignedUrl: string | null;
  beats: NarrativeBeat[];
  alignmentCoverage: number | null;
}

// ═══ TTS 配置 ═══
export interface TTSEngineConfig {
  id: string;
  name: string;
  code: string;
  providerType: "volcengine";
  endpoint: string;
  resourceId: string;
  timeoutSeconds: number;
  isActive: boolean;
  apiKeySet: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface TTSVoice {
  id: string;
  engineId: string;
  name: string;
  speakerId: string;
  language: string;
  gender: string | null;
  description: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface TTSSettingsResponse {
  engines: TTSEngineConfig[];
  voices: TTSVoice[];
}
