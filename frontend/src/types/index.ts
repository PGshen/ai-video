// ═══ 选题 ═══
export interface TopicScores {
  counterintuitive: number;
  defensibility: number;
  visual: number;
  freshness: number;
}

export interface Topic {
  id: string;
  title: string;
  description: string;
  source: "manual" | "ai_brainstorm" | "audience" | "competitor";
  status: "pending" | "stocked" | "in_production" | "used" | "abandoned";
  scores: TopicScores;
  compositeScore: number;
  performanceScore: number | null;
  tags: string[];
  needsRecheck: boolean;
  createdAt: string;
  updatedAt: string;
}

// ═══ 视频项目 ═══
export type ProjectStatus =
  | "draft"
  | "script_generating"
  | "script_failed"
  | "script_review"
  | "video_generating"
  | "video_failed"
  | "video_review"
  | "published"
  | "abandoned";

export interface VideoProject {
  id: string;
  topicId: string;
  status: ProjectStatus;
  renderEngine: "manim" | "remotion";
  ttsVoice: string;
  aspectRatio: "landscape" | "portrait";
  currentScriptVersion: ScriptVersion | null;
  currentVideoAsset: VideoAsset | null;
  retryCount: number;
  createdAt: string;
  updatedAt: string;
}

// ═══ 镜头 ═══
export interface Scene {
  sceneIndex: number;
  narration: string;
  description: string;
  code: string;
  estimatedDurationSeconds: number;
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

// ═══ 脚本版本 ═══
export interface ScriptVersion {
  id: string;
  projectId: string;
  versionNumber: number;
  scenes: Scene[];
  factChecks: FactCheckItem[];
  renderEngine: "manim" | "remotion";
  aiModel: string;
  rejectionContext: RejectionContext | null;
  createdAt: string;
}

// ═══ 视频产物 ═══
export interface VideoAsset {
  id: string;
  projectId: string;
  scriptVersionId: string;
  videoFileKey: string;
  durationSeconds: number;
  resolution: string;
  status: "rendering" | "completed" | "failed";
  createdAt: string;
}

// ═══ 审核请求 ═══
export interface ReviewRequest {
  gate: "script" | "video";
  verdict: "approved" | "rejected" | "abandoned";
  rejectionType?: "topic_invalid" | "fact_error" | "script_weak" | "sync_issue";
  rejectionDetail?: string;
  targetStage?: "script_generating";
  factCheckVerdicts?: Array<{
    index: number;
    verdict: "approved" | "rejected" | "needs_revision";
    note: string;
  }>;
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
  taskType: "generate_script" | "render_video";
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
