// frontend/src/components/ui/chat-message.tsx
// 手动创建最小版 — 正式安装时删除此文件替换为 simple-ai 版本

import * as React from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import { cn } from "@/lib/utils";

function withoutNode<T extends { node?: unknown }>(props: T) {
  const { node, ...rest } = props;
  void node;
  return rest;
}

const markdownComponents: Components = {
  h1(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <h1
        {...rest}
        className={cn("mt-5 mb-2 text-xl font-semibold leading-snug first:mt-0", className)}
      />
    );
  },
  h2(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <h2
        {...rest}
        className={cn("mt-5 mb-2 text-lg font-semibold leading-snug first:mt-0", className)}
      />
    );
  },
  h3(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <h3
        {...rest}
        className={cn("mt-4 mb-2 text-base font-semibold leading-snug first:mt-0", className)}
      />
    );
  },
  p(props) {
    const { className, ...rest } = withoutNode(props);
    return <p {...rest} className={cn("my-2 leading-6 first:mt-0 last:mb-0", className)} />;
  },
  ul(props) {
    const { className, ...rest } = withoutNode(props);
    return <ul {...rest} className={cn("my-2 ml-5 list-disc space-y-1", className)} />;
  },
  ol(props) {
    const { className, ...rest } = withoutNode(props);
    return <ol {...rest} className={cn("my-2 ml-5 list-decimal space-y-1", className)} />;
  },
  li(props) {
    const { className, ...rest } = withoutNode(props);
    return <li {...rest} className={cn("pl-1 leading-6", className)} />;
  },
  blockquote(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <blockquote
        {...rest}
        className={cn("my-3 border-l-2 border-border pl-3 text-muted-foreground", className)}
      />
    );
  },
  strong(props) {
    const { className, ...rest } = withoutNode(props);
    return <strong {...rest} className={cn("font-semibold text-foreground", className)} />;
  },
  a(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <a
        {...rest}
        className={cn("font-medium underline underline-offset-4", className)}
        target="_blank"
        rel="noreferrer"
      />
    );
  },
  code(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <code
        {...rest}
        className={cn(
          "rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground",
          className
        )}
      />
    );
  },
  pre(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <pre
        {...rest}
        className={cn("my-3 overflow-x-auto rounded-md bg-muted p-3 text-xs leading-5", className)}
      />
    );
  },
  table(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <div className="my-3 block w-full min-w-0 max-w-full overflow-x-auto rounded-md border">
        <table {...rest} className={cn("w-full table-fixed border-collapse text-left text-sm", className)} />
      </div>
    );
  },
  thead(props) {
    const { className, ...rest } = withoutNode(props);
    return <thead {...rest} className={cn("bg-muted/70", className)} />;
  },
  tr(props) {
    const { className, ...rest } = withoutNode(props);
    return <tr {...rest} className={cn("border-b last:border-b-0", className)} />;
  },
  th(props) {
    const { className, ...rest } = withoutNode(props);
    return (
      <th
        {...rest}
        className={cn("break-words px-3 py-2 align-top font-semibold text-foreground", className)}
      />
    );
  },
  td(props) {
    const { className, ...rest } = withoutNode(props);
    return <td {...rest} className={cn("break-words px-3 py-2 align-top leading-6", className)} />;
  },
};

const COMMON_TEX_COMMAND = /\\(?:frac|sqrt|rho|alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|omega|cdot|times|le|ge|approx|sum|int|lim|infty|mathrm|text|sin|cos|tan|log|ln|exp|left|right)\b/;
const CJK_CHARACTER = /[\u3400-\u9fff]/;

function normalizeMathDelimiters(content: string): string {
  return content
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, formula: string) => `$$\n${formula.trim()}\n$$`)
    .replace(/\\\(((?:.|\n)*?)\\\)/g, (_, formula: string) => `$${formula.trim()}$`)
    .replace(/\(([^()\n]{1,180})\)/g, (match, formula: string) => {
      const trimmed = formula.trim();
      if (CJK_CHARACTER.test(trimmed) || !/[A-Za-z0-9]/.test(trimmed)) {
        return match;
      }
      if (COMMON_TEX_COMMAND.test(trimmed) || /[_^=]/.test(trimmed)) {
        return `$${trimmed}$`;
      }
      return match;
    });
}

export function ChatMessageMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={markdownComponents}
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
    >
      {normalizeMathDelimiters(content)}
    </ReactMarkdown>
  );
}
export function ChatMessage({ children }: { children: React.ReactNode }) {
  return <div className="py-3">{children}</div>;
}
export function ChatMessageContent({ children }: { children: React.ReactNode }) {
  return <div className="text-sm">{children}</div>;
}
