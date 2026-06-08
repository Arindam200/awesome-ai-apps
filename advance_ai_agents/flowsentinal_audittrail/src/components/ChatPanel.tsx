"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Sparkles, Send, Workflow, RotateCcw, Copy, Check } from "lucide-react";
import clsx from "clsx";
import ReactMarkdown from "react-markdown";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: { tokens?: number; latency_ms?: number; web_sources?: number };
}

interface ChatPanelProps {
  onWorkflowPlan?: (plan: {
    analysis: string;
    suggestedSteps: string[];
    canAutomate: boolean;
  }) => void;
}

const PROMPTS = [
  "Analyze the top AI infrastructure pricing trends this quarter",
  "Research recent LLM API performance benchmarks",
  "Summarize competitor product launches from last month",
];

function MessageBubble({ msg }: { msg: Message }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] group">
          <div className="bg-violet-600/20 border border-violet-500/20 rounded-2xl rounded-tr-sm px-4 py-3 text-[14px] leading-relaxed text-ink-primary">
            {msg.content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      {/* AI avatar */}
      <div className="w-7 h-7 rounded-xl bg-gradient-violet flex items-center justify-center flex-shrink-0 mt-0.5 shadow-glow-violet">
        <Sparkles className="w-3.5 h-3.5 text-white" strokeWidth={2.5} />
      </div>

      <div className="flex-1 min-w-0 group">
        <div className="bg-surface-2 border border-border-1 rounded-2xl rounded-tl-sm px-4 py-3">
          <div className="prose prose-invert prose-sm max-w-none text-[14px] leading-relaxed text-ink-primary
            [&_h2]:text-[13px] [&_h2]:font-semibold [&_h2]:text-ink-primary [&_h2]:mt-4 [&_h2]:mb-1.5 [&_h2]:first:mt-0
            [&_h3]:text-[13px] [&_h3]:font-medium [&_h3]:text-ink-secondary [&_h3]:mt-3 [&_h3]:mb-1
            [&_p]:text-ink-primary [&_p]:leading-relaxed [&_p]:my-1.5
            [&_ul]:pl-4 [&_ul]:my-1.5 [&_ul]:space-y-1
            [&_ol]:pl-4 [&_ol]:my-1.5 [&_ol]:space-y-1
            [&_li]:text-ink-primary [&_li]:text-[13px]
            [&_strong]:text-ink-primary [&_strong]:font-semibold
            [&_a]:text-violet-400 [&_a]:underline [&_a]:underline-offset-2 [&_a:hover]:text-violet-300
            [&_code]:bg-surface-3 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-[12px] [&_code]:font-mono [&_code]:text-violet-300
            [&_pre]:bg-surface-3 [&_pre]:rounded-xl [&_pre]:p-3 [&_pre]:overflow-x-auto [&_pre]:my-2
            [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-ink-secondary
            [&_hr]:border-border-1 [&_hr]:my-3
            [&_blockquote]:border-l-2 [&_blockquote]:border-violet-500/40 [&_blockquote]:pl-3 [&_blockquote]:text-ink-muted [&_blockquote]:italic">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between mt-2.5 pt-2.5 border-t border-border-1">
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-ink-muted font-medium">Nemotron Super</span>
              {msg.meta?.tokens && (
                <span className="text-[11px] text-ink-muted">{msg.meta.tokens.toLocaleString()} tokens</span>
              )}
              {msg.meta?.latency_ms && (
                <span className="text-[11px] text-ink-muted">{(msg.meta.latency_ms / 1000).toFixed(1)}s</span>
              )}
              {typeof msg.meta?.web_sources === "number" && msg.meta.web_sources > 0 && (
                <span className="text-[11px] text-emerald-400">{msg.meta.web_sources} live sources</span>
              )}
            </div>
            <button
              onClick={copy}
              className="opacity-0 group-hover:opacity-100 flex items-center gap-1.5 text-[11px] text-ink-muted hover:text-ink-secondary transition-all"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-xl bg-gradient-violet flex items-center justify-center flex-shrink-0 shadow-glow-violet">
        <Sparkles className="w-3.5 h-3.5 text-white" strokeWidth={2.5} />
      </div>
      <div className="bg-surface-2 border border-border-1 rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="flex items-center gap-1 h-5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-violet-400/60 animate-bounce-dots"
              style={{ animationDelay: `${i * 0.16}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ChatPanel({ onWorkflowPlan }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  };

  const summarizeOutputs = (outputs: unknown): string => {
    try {
      const text = JSON.stringify(outputs ?? {});
      return text.length > 240 ? `${text.slice(0, 240)}...` : text;
    } catch {
      return "Output available";
    }
  };

  const send = useCallback(async (mode: "chat" | "workflow_plan" = "chat", override?: string) => {
    const text = (override ?? input).trim();
    if (!text || loading) return;

    const userMsg: Message = { id: `u${Date.now()}`, role: "user", content: text };
    setMessages((p) => [...p, userMsg]);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setLoading(true);

    try {
      const history = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }));
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history, mode }),
      });
      const data = await res.json();

      if (mode === "workflow_plan" && data.plan) {
        onWorkflowPlan?.(data.plan);
        const steps: string[] = data.plan.suggestedSteps;
        setMessages((p) => [
          ...p,
          {
            id: `a${Date.now()}`,
            role: "assistant",
            content: `${data.plan.analysis}\n\nPipeline stages:\n${steps.map((s, i) => `${i + 1}. ${s}`).join("\n")}\n\nThis workflow ${data.plan.canAutomate ? "can be fully automated" : "may need manual review"} via n8n.`,
          },
        ]);

        // Auto-trigger n8n after plan generation.
        const workflowRes = await fetch("/api/workflow", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inputs: {
              query: text,
              analysis: data.plan.analysis,
              steps: steps.join(" | "),
            },
          }),
        });
        const workflowData = await workflowRes.json();
        if (workflowData.error) {
          setMessages((p) => [
            ...p,
            {
              id: `wfe${Date.now()}`,
              role: "assistant",
              content: `n8n auto-run failed: ${workflowData.error}`,
            },
          ]);
        } else {
          setMessages((p) => [
            ...p,
            {
              id: `wfs${Date.now()}`,
              role: "assistant",
              content: `n8n auto-run complete.\nRun: ${workflowData.run_id}\nState: ${workflowData.state}\nOutputs: ${summarizeOutputs(workflowData.outputs)}`,
            },
          ]);
        }
      } else if (data.content) {
        setMessages((p) => [
          ...p,
          {
            id: `a${Date.now()}`,
            role: "assistant",
            content: data.content,
            meta: {
              tokens: data.usage?.total_tokens,
              latency_ms: data.latency_ms,
              web_sources: data.web_sources,
            },
          },
        ]);
      } else if (data.error) {
        setMessages((p) => [
          ...p,
          { id: `e${Date.now()}`, role: "assistant", content: `Something went wrong: ${data.error}` },
        ]);
      }
    } catch (err) {
      setMessages((p) => [
        ...p,
        { id: `e${Date.now()}`, role: "assistant", content: `Network error. Please try again.` },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, messages, loading, onWorkflowPlan]);

  const sendPlan = () => {
    const candidate = input.trim();
    if (!candidate || loading) return;
    send("workflow_plan", candidate);
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send("chat");
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Panel header */}
      <div className="px-5 py-3.5 border-b border-border-1 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-lg bg-gradient-violet flex items-center justify-center">
            <Sparkles className="w-3 h-3 text-white" />
          </div>
          <span className="text-[13px] font-semibold text-ink-primary">AI Assistant</span>
          <span className="px-2 py-0.5 rounded-full bg-violet-500/10 border border-violet-500/20 text-[10px] font-medium text-violet-300">
            Nebius · Nemotron Super
          </span>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="p-1.5 rounded-lg hover:bg-surface-3 text-ink-muted hover:text-ink-secondary transition-colors"
            title="Clear chat"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center gap-6 animate-fade-in">
            {/* Hero icon */}
            <div className="w-14 h-14 rounded-2xl bg-gradient-violet flex items-center justify-center shadow-glow-violet">
              <Sparkles className="w-7 h-7 text-white" />
            </div>
            <div className="text-center">
              <h3 className="text-[15px] font-semibold text-ink-primary mb-1">How can I help?</h3>
              <p className="text-[13px] text-ink-muted max-w-xs">
                Ask anything or use the <strong className="text-ink-secondary">Plan</strong> button to convert your request into an automated workflow.
              </p>
              <p className="text-[12px] text-ink-muted/80 mt-2 max-w-sm">
                Time-sensitive questions (latest/news/updates) use live web research with source-grounded answers.
              </p>
            </div>

            {/* Prompt suggestions */}
            <div className="w-full max-w-md space-y-2">
              {PROMPTS.map((p, i) => (
                <button
                  key={i}
                  onClick={() => send("chat", p)}
                  className="w-full text-left px-4 py-3 rounded-xl bg-surface-2 border border-border-1 hover:border-border-2 hover:bg-surface-3 transition-all group"
                >
                  <span className="text-[13px] text-ink-secondary group-hover:text-ink-primary transition-colors leading-relaxed">
                    {p}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className="message-in">
            <MessageBubble msg={msg} />
          </div>
        ))}

        {loading && (
          <div className="animate-fade-in">
            <TypingIndicator />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="px-5 pb-5 pt-3 flex-shrink-0">
        <div className="bg-surface-2 border border-border-1 rounded-2xl focus-within:border-border-2 focus-within:shadow-glow-violet transition-all">
          <textarea
            ref={textareaRef}
            rows={1}
            className="w-full bg-transparent px-4 pt-3.5 pb-0 text-[14px] text-ink-primary placeholder-ink-muted resize-none outline-none leading-relaxed"
            placeholder="Ask anything..."
            value={input}
            onChange={(e) => { setInput(e.target.value); autoResize(); }}
            onKeyDown={handleKey}
            disabled={loading}
          />
          <div className="flex items-center justify-between px-3 pb-3 pt-2">
            <p className="text-[11px] text-ink-muted">
              <kbd className="px-1.5 py-0.5 rounded bg-surface-3 text-[10px] font-mono border border-border-1">↵</kbd>
              {" "}to send · <kbd className="px-1.5 py-0.5 rounded bg-surface-3 text-[10px] font-mono border border-border-1">Shift+↵</kbd>
              {" "}new line
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={sendPlan}
                disabled={!input.trim() || loading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[12px] font-medium text-ink-secondary bg-surface-3 border border-border-1 hover:border-border-2 hover:text-ink-primary transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                title={input.trim() ? "Generate workflow plan" : "Type a message first"}
              >
                <Workflow className="w-3.5 h-3.5" />
                Plan
              </button>
              <button
                onClick={() => send("chat")}
                disabled={!input.trim() || loading}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-[12px] font-semibold text-white bg-violet-600 hover:bg-violet-500 transition-colors shadow-glow-violet disabled:opacity-40 disabled:cursor-not-allowed active:scale-95"
              >
                <Send className="w-3.5 h-3.5" />
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
