export const STYLE_CATEGORIES = [
  { key: "narrative_style", label: "叙事风格" },
  { key: "pacing", label: "叙事节奏" },
  { key: "scene_structure", label: "镜头结构" },
  { key: "color_scheme", label: "视觉系统" },
  { key: "animation_style", label: "动画系统" },
] as const;

export type StyleCategoryKey = typeof STYLE_CATEGORIES[number]["key"];
