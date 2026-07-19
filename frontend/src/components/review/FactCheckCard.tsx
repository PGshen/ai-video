import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { FactCheckItem } from "@/types";

type Verdict = "approved" | "rejected" | "needs_revision";

interface FactCheckCardProps {
  item: FactCheckItem;
  index: number;
  verdict: Verdict | null;
  note: string;
  onVerdictChange: (index: number, verdict: Verdict, note: string) => void;
}

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-red-100 text-red-800",
};

export function FactCheckCard({
  item,
  index,
  verdict,
  note,
  onVerdictChange,
}: FactCheckCardProps) {
  const [localNote, setLocalNote] = useState(note);

  const handleVerdictClick = (v: Verdict) => {
    onVerdictChange(index, v, localNote);
  };

  const handleNoteChange = (n: string) => {
    setLocalNote(n);
    if (verdict) {
      onVerdictChange(index, verdict, n);
    }
  };

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="space-y-2">
        <p className="text-sm font-medium leading-snug">{item.claimText}</p>
        <div className="flex items-center gap-1">
          <Badge variant="outline" className="text-xs">镜头 {item.sceneIndex}</Badge>
          <Badge className={`text-xs ${CONFIDENCE_COLOR[item.confidence] ?? ""}`}>
            {item.confidence}
          </Badge>
          {item.isHypothesis && (
            <Badge variant="secondary" className="text-xs">假设</Badge>
          )}
        </div>
      </div>

      {item.sourceDescription && (
        <p className="text-xs text-muted-foreground">
          来源：{item.sourceUrl ? (
            <a href={item.sourceUrl} target="_blank" rel="noreferrer" className="underline">
              {item.sourceDescription}
            </a>
          ) : item.sourceDescription}
        </p>
      )}

      {item.controversy && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
          争议：{item.controversy}
        </p>
      )}

      {item.assumptions && (
        <p className="text-xs text-muted-foreground">假设条件：{item.assumptions}</p>
      )}

      <div className="flex gap-2 pt-1">
        {(["approved", "needs_revision", "rejected"] as Verdict[]).map((v) => (
          <button
            key={v}
            onClick={() => handleVerdictClick(v)}
            className={[
              "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
              verdict === v
                ? v === "approved"
                  ? "bg-green-500 text-white border-green-500"
                  : v === "rejected"
                  ? "bg-red-500 text-white border-red-500"
                  : "bg-yellow-500 text-white border-yellow-500"
                : "bg-background border-border text-muted-foreground hover:bg-muted",
            ].join(" ")}
          >
            {v === "approved" ? "通过" : v === "rejected" ? "驳回" : "需修改"}
          </button>
        ))}
      </div>

      {verdict && verdict !== "approved" && (
        <div className="space-y-1">
          <Label className="text-xs">审核备注</Label>
          <Textarea
            value={localNote}
            onChange={(e) => handleNoteChange(e.target.value)}
            placeholder="请说明问题..."
            className="text-xs min-h-[60px]"
          />
        </div>
      )}
    </div>
  );
}
