export const STYLE_CATEGORIES = [
  { key: "narrative_style", label: "叙事蓝图" },
  { key: "color_scheme", label: "视觉系统" },
  { key: "animation_style", label: "动画系统" },
  { key: "exemplar", label: "金样本" },
] as const;

export type StyleCategoryKey = typeof STYLE_CATEGORIES[number]["key"];
