import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { SendHorizontal } from "lucide-react";
import { ChatMessageMarkdown } from "@/components/ui/chat-message";
import type { Topic, ResearchMessage } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

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
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
      <ChatMessageMarkdown content={entry.text || "▋"} />
    </div>
  );
}

interface Props {
  topic: Topic;
}

export function ResearchChat({ topic }: Props) {
  const [entries, setEntries] = useState<ChatEntry[]>(() =>
    toEntries(topic.researchData ?? [])
  );
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  // Re-sync when topic changes (panel re-opened with different topic)
  useEffect(() => {
    setEntries(toEntries(topic.researchData ?? []));
  }, [topic.id]);

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
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
        body: JSON.stringify({ message, use_default_prompt: useDefaultPrompt }),
      });

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
          setEntries((prev) =>
            prev.map((e) =>
              e.id === assistantEntry.id
                ? { ...e, text: e.text + payload }
                : e
            )
          );
        }
        if (shouldStop) {
          reader.cancel();
          break;
        }
      }
    } finally {
      setStreaming(false);
    }
  }

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
    <div className="flex flex-col h-full min-h-0">
      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-4 pr-1"
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

      {/* Input area */}
      <form onSubmit={handleSubmit} className="flex gap-2 pt-3 border-t mt-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          className="resize-none text-sm min-h-[40px] max-h-[120px]"
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
