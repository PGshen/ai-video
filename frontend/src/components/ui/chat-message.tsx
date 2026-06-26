// frontend/src/components/ui/chat-message.tsx
// 手动创建最小版 — 正式安装时删除此文件替换为 simple-ai 版本

import * as React from "react";
import ReactMarkdown from "react-markdown";

export function ChatMessageMarkdown({ content }: { content: string }) {
  return <ReactMarkdown>{content}</ReactMarkdown>;
}
export function ChatMessage({ children }: { children: React.ReactNode }) {
  return <div className="py-3">{children}</div>;
}
export function ChatMessageContent({ children }: { children: React.ReactNode }) {
  return <div className="text-sm">{children}</div>;
}
