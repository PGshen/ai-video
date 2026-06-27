export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 30) return `${days} 天前`;
  const months = Math.floor(days / 30);
  return `${months} 个月前`;
}

export const SOURCE_LABELS: Record<string, string> = {
  manual: "手动",
  ai_brainstorm: "AI 生成",
  audience: "受众",
  competitor: "竞品",
};

export const TOPIC_STATUS_LABELS: Record<string, string> = {
  pending: "待评估",
  stocked: "已入库",
  in_production: "制作中",
  used: "已使用",
  abandoned: "已废弃",
};

export const TOPIC_STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  stocked: "bg-blue-100 text-blue-700",
  in_production: "bg-orange-100 text-orange-700",
  used: "bg-green-100 text-green-700",
  abandoned: "bg-red-100 text-red-700",
};

export const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  narrative_generating: "生成叙事中",
  narrative_review: "叙事待审核",
  narrative_failed: "叙事生成失败",
  code_generating: "生成代码中",
  code_failed: "代码生成失败",
  script_review: "脚本待审核",
  video_generating: "生成视频中",
  video_failed: "视频失败",
  video_review: "视频待审核",
  published: "已发布",
  abandoned: "已废弃",
};

export const PROJECT_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  narrative_generating: "bg-blue-100 text-blue-700",
  narrative_review: "bg-yellow-100 text-yellow-700",
  narrative_failed: "bg-red-100 text-red-700",
  code_generating: "bg-blue-100 text-blue-700",
  code_failed: "bg-red-100 text-red-700",
  script_review: "bg-yellow-100 text-yellow-700",
  video_generating: "bg-purple-100 text-purple-700",
  video_failed: "bg-red-100 text-red-700",
  video_review: "bg-yellow-100 text-yellow-700",
  published: "bg-green-100 text-green-700",
  abandoned: "bg-gray-100 text-gray-500",
};
