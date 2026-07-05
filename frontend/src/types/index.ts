// ═══ 选题 ═══
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
  aspectRatio: "landscape" | "portrait";
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
export interface RejectionContext {
  rejectionType: string;
  rejectionDetail: string;
  targetStage: string;
  rejectedAt: string;
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
