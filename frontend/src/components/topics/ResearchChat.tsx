import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, SendHorizontal } from "lucide-react";
import { ChatMessageMarkdown } from "@/components/ui/chat-message";
import type { Topic, ResearchMessage } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
}

function toEntries(messages: ResearchMessage[]): ChatEntry[] {
  return messages.map((m, i) => ({
    id: String(i),
    role: m.role,
    text: m.content,
  }));
}

function MessageBubble({ entry }: { entry: ChatEntry }) {
  if (entry.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-muted rounded-lg px-3 py-2 text-sm max-w-[85%]">
          {entry.text}
        </div>
      </div>
    );
  }
  if (!entry.text) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex items-center gap-2 py-1 text-sm text-muted-foreground"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        <span>正在研究…</span>
      </div>
    );
  }
  return (
    <div className="min-w-0 max-w-full text-sm">
      <ChatMessageMarkdown content={entry.text} />
    </div>
  );
}

function decodeResearchPayload(payload: string): string {
  try {
    const parsed: unknown = JSON.parse(payload);
    if (typeof parsed === "string") {
      return parsed;
    }
    if (
      parsed &&
      typeof parsed === "object" &&
      "content" in parsed &&
      typeof parsed.content === "string"
    ) {
      return parsed.content;
    }
  } catch {
    // Keep compatibility with the previous plain-text SSE format.
  }
  return payload;
}

interface Props {
  topic: Topic;
  onSnippetSelect: (text: string) => void;
}

export function ResearchChat({ topic, onSnippetSelect }: Props) {
  const [entries, setEntries] = useState<ChatEntry[]>(() =>
    toEntries(topic.researchData ?? [])
  );
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [bubble, setBubble] = useState<{ x: number; y: number; text: string } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  // Re-sync when topic changes (panel re-opened with different topic)
  useEffect(() => {
    setEntries(toEntries(topic.researchData ?? []));
  }, [topic.id, topic.researchData]);

  async function send(message: string, useDefaultPrompt: boolean) {
    const userEntry: ChatEntry = {
      id: Date.now() + "-u",
      role: "user",
      text: useDefaultPrompt ? "请介绍这个选题的背景知识和核心理论" : message,
    };
    const assistantEntry: ChatEntry = {
      id: Date.now() + "-a",
      role: "assistant",
      text: "",
    };
    setEntries((prev) => [...prev, userEntry, assistantEntry]);
    setInput("");
    setStreaming(true);

    try {
      const res = await fetch(`${BASE_URL}/api/topics/${topic.id}/research`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message, use_default_prompt: useDefaultPrompt }),
      });

      if (res.status === 401) {
        window.dispatchEvent(new CustomEvent("auth:unauthorized"));
      }

      if (!res.ok || !res.body) {
        setEntries((prev) =>
          prev.map((e) =>
            e.id === assistantEntry.id
              ? { ...e, text: `请求失败 (${res.status})，请重试` }
              : e
          )
        );
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let shouldStop = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]") {
            shouldStop = true;
            break;
          }
          if (payload.startsWith("[ERROR]")) {
            setEntries((prev) =>
              prev.map((e) =>
                e.id === assistantEntry.id
                  ? { ...e, text: "查询失败，请重试" }
                  : e
              )
            );
            shouldStop = true;
            break;
          }
          const content = decodeResearchPayload(payload);
          setEntries((prev) =>
            prev.map((e) =>
              e.id === assistantEntry.id
                ? { ...e, text: e.text + content }
                : e
            )
          );
        }
        if (shouldStop) {
          reader.cancel();
          break;
        }
      }
    } catch {
      setEntries((prev) =>
        prev.map((e) =>
          e.id === assistantEntry.id && !e.text
            ? { ...e, text: "网络异常，请稍后重试" }
            : e
        )
      );
    } finally {
      setStreaming(false);
    }
  }

  function handleMouseUp() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) {
      setBubble(null);
      return;
    }
    const text = sel.toString().trim();
    if (!text) {
      setBubble(null);
      return;
    }
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    setBubble({
      x: Math.min(rect.right, window.innerWidth - 148),
      y: rect.top - 36,
      text,
    });
  }

  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-snippet-bubble]")) {
        setBubble(null);
      }
    }
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || streaming) return;
    send(input.trim(), false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!input.trim() || streaming) return;
      send(input.trim(), false);
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0 min-w-0">
      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 min-w-0 overflow-y-auto space-y-4 pr-1"
        onMouseUp={handleMouseUp}
      >
        {entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <p className="text-sm text-muted-foreground">
              使用 AI 查询该选题的背景资料，辅助打分判断
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => send("", true)}
              disabled={streaming}
            >
              查询背景资料
            </Button>
          </div>
        ) : (
          entries.map((entry) => <MessageBubble key={entry.id} entry={entry} />)
        )}
      </div>

      {bubble && createPortal(
        <div
          data-snippet-bubble
          style={{ position: "fixed", left: bubble.x, top: bubble.y }}
          className="z-50 bg-foreground text-background text-xs px-2 py-1 rounded shadow-md cursor-pointer whitespace-nowrap"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            onSnippetSelect(bubble.text);
            window.getSelection()?.removeAllRanges();
            setBubble(null);
          }}
        >
          ＋ 加入上下文
        </div>,
        document.body
      )}

      {/* Input area */}
      <form onSubmit={handleSubmit} className="flex min-w-0 gap-2 pt-3 border-t mt-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          className="min-w-0 resize-none text-sm min-h-[40px] max-h-[120px]"
          rows={1}
          disabled={streaming}
        />
        <Button
          type="submit"
          size="icon"
          disabled={!input.trim() || streaming}
          className="shrink-0 self-end"
        >
          <SendHorizontal className="w-4 h-4" />
        </Button>
      </form>
    </div>
  );
}
