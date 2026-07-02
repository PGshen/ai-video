import { Badge } from "@/components/ui/badge";
import type { NarrativeBeat } from "@/types";

const TRANSITION_LABELS: Record<NarrativeBeat["transition"], string> = {
  continue: "延续",
  transform: "变形",
  reveal: "揭示",
  replace: "替换",
  exit: "退场",
};

const ALIGNMENT_LABELS: Record<NarrativeBeat["alignmentStatus"], string> = {
  pending: "待对齐",
  aligned: "已对齐",
  interpolated: "已插值",
  failed: "对齐失败",
};

function formatRange(start: number | null, end: number | null) {
  if (start == null || end == null) return null;
  return `${start.toFixed(2)}–${end.toFixed(2)}s`;
}

function alignmentVariant(
  status: NarrativeBeat["alignmentStatus"]
): "default" | "secondary" | "outline" | "destructive" {
  if (status === "aligned") return "default";
  if (status === "interpolated") return "secondary";
  if (status === "failed") return "destructive";
  return "outline";
}

interface SceneBeatsProps {
  beats: NarrativeBeat[];
  defaultOpen?: boolean;
}

export function SceneBeats({ beats, defaultOpen = true }: SceneBeatsProps) {
  if (!beats.length) return null;

  return (
    <details className="rounded-md border bg-muted/15 text-xs" open={defaultOpen}>
      <summary className="cursor-pointer select-none px-3 py-2 font-medium text-muted-foreground hover:text-foreground">
        语义节拍（{beats.length}）
      </summary>
      <div className="space-y-2 border-t p-2">
        {beats.map((beat) => {
          const speechRange = formatRange(
            beat.speechStartSeconds,
            beat.speechEndSeconds
          );
          const animationRange = formatRange(
            beat.animationStartSeconds,
            beat.animationEndSeconds
          );

          return (
            <div
              key={beat.beatIndex}
              className="rounded border bg-background px-3 py-2.5 space-y-1.5"
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge variant="outline" className="text-[11px]">
                  Beat {beat.beatIndex + 1}
                </Badge>
                <Badge
                  variant={alignmentVariant(beat.alignmentStatus)}
                  className="text-[11px]"
                >
                  {ALIGNMENT_LABELS[beat.alignmentStatus]}
                </Badge>
                <Badge variant="secondary" className="text-[11px]">
                  {TRANSITION_LABELS[beat.transition]}
                </Badge>
                {speechRange && (
                  <span className="text-[11px] text-muted-foreground">
                    语音 {speechRange}
                  </span>
                )}
                {animationRange && (
                  <span className="text-[11px] text-muted-foreground">
                    动画 {animationRange}
                  </span>
                )}
              </div>
              <p className="font-medium leading-relaxed">{beat.cueText}</p>
              <p className="leading-relaxed text-muted-foreground">
                {beat.visualAction}
              </p>
              {beat.emphasis && (
                <p className="text-[11px] text-muted-foreground">
                  强调：{beat.emphasis}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </details>
  );
}
