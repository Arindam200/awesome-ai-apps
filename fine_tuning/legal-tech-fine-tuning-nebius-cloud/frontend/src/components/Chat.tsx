import { useEffect, useRef, useState } from 'react'
import { legalAnalyze } from '../lib/legalAnalyze'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

function id() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function ThinkingIndicator() {
  return (
    <span className="inline-flex animate-pulse items-center gap-1" aria-hidden>
      <span>·</span>
      <span>·</span>
      <span>·</span>
    </span>
  )
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: id(),
      role: 'assistant',
      content:
        'Welcome to Shivay. Ask a legal question below — answers come from your connected legal model.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  async function send() {
    const trimmed = input.trim()
    if (!trimmed || loading) return

    setError(null)
    const userMsg: Message = { id: id(), role: 'user', content: trimmed }
    setMessages((m) => [...m, userMsg])
    setInput('')
    setLoading(true)

    const assistantId = id()

    try {
      await legalAnalyze(
        {
          query: trimmed,
          max_tokens: 512,
          temperature: 0.3,
        },
        {
          onDelta: (text) => {
            setLoading(false)
            setMessages((m) => {
              const has = m.some((mes) => mes.id === assistantId)
              if (!has) {
                return [
                  ...m,
                  { id: assistantId, role: 'assistant', content: text },
                ]
              }
              return m.map((mes) =>
                mes.id === assistantId ? { ...mes, content: text } : mes,
              )
            })
          },
        },
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-1 py-2">
        <div className="mx-auto flex max-w-3xl flex-col gap-3">
          {messages.map((m) => (
            <div
              key={m.id}
              className={
                m.role === 'user'
                  ? 'ml-auto max-w-[min(100%,520px)] rounded-lg bg-[#4A7C7E] px-4 py-3 text-[15px] leading-relaxed text-white'
                  : 'mr-auto max-w-[min(100%,560px)] rounded-lg border-[0.5px] border-[#E5E5E5] bg-[#EEF4F4] px-4 py-3 text-[15px] leading-relaxed text-[#1a1a1a] whitespace-pre-wrap'
              }
            >
              {m.content}
            </div>
          ))}
          {loading && (
            <div className="mr-auto max-w-[min(100%,560px)] rounded-lg border-[0.5px] border-[#E5E5E5] bg-[#EEF4F4] px-4 py-3 text-[15px] text-[#888]">
              <span className="inline-flex items-center gap-1">
                Shivay is thinking
                <ThinkingIndicator />
              </span>
            </div>
          )}
          {error && (
            <p className="text-center text-sm text-red-600" role="alert">
              {error}
            </p>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0 border-t-[0.5px] border-[#E5E5E5] bg-white px-1 py-4">
        <div className="mx-auto max-w-3xl">
          <div className="flex h-10 items-center gap-2 rounded-lg border-[0.5px] border-[#ddd] bg-white px-3">
            <svg
              className="shrink-0 text-[#aaa]"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.2-4.2" />
            </svg>
            <input
              ref={inputRef}
              id="shivay-input"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void send()
                }
              }}
              placeholder="Ask Shivay a legal question…"
              className="min-h-[40px] flex-1 bg-transparent text-[15px] text-[#1a1a1a] outline-none placeholder:text-[#aaa]"
              disabled={loading}
              aria-label="Message"
            />
            <kbd className="hidden shrink-0 rounded border-[0.5px] border-[#ddd] bg-[#fafafa] px-1.5 py-0.5 text-[11px] text-[#888] sm:inline">
              ⌘K
            </kbd>
            <button
              type="button"
              onClick={() => void send()}
              disabled={loading || !input.trim()}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#4A7C7E] text-white transition hover:bg-[#3d696b] disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Send message"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M22 2 11 13" />
                <path d="M22 2 15 22 11 13 2 9 22 2z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
