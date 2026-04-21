import { useState } from 'react'

type NavItem =
  | { label: string; locked?: false; active?: boolean }
  | { label: string; locked: true }

function NavRow({ item }: { item: NavItem }) {
  const locked = 'locked' in item && item.locked
  const active = 'active' in item && item.active

  if (locked) {
    return (
      <div
        className="flex cursor-default items-center gap-2 rounded-md px-3 py-2 text-[13px] text-[#bbb] opacity-40"
        aria-disabled
      >
        <span className="min-w-0 truncate">{item.label}</span>
        <span className="shrink-0 text-[11px]" aria-hidden>
          🔒
        </span>
      </div>
    )
  }

  return (
    <button
      type="button"
      className={
        active
          ? 'w-full rounded-[6px] bg-[#4A7C7E] px-3 py-2 text-left text-[13px] font-medium text-white'
          : 'w-full rounded-md px-3 py-2 text-left text-[13px] text-[#666] hover:bg-[#F5F5F5]'
      }
    >
      {item.label}
    </button>
  )
}

function Section({
  title,
  lockedHeader,
  defaultOpen = true,
  children,
}: {
  title: string
  lockedHeader?: boolean
  defaultOpen?: boolean
  children?: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  if (lockedHeader) {
    return (
      <div className="mb-1 opacity-40">
        <div className="mb-1 px-1 py-1 text-[10px] font-normal uppercase tracking-[0.08em] text-[#aaa]">
          {title}{' '}
          <span className="inline" aria-hidden>
            🔒
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mb-1 flex w-full items-center justify-between gap-1 px-1 py-1 text-left"
      >
        <span className="text-[10px] font-normal uppercase tracking-[0.08em] text-[#aaa]">
          {title}
        </span>
        <span className="text-[10px] text-[#aaa]" aria-hidden>
          {open ? '▾' : '▸'}
        </span>
      </button>
      {open && children && (
        <div className="flex flex-col gap-0.5 pl-0">{children}</div>
      )}
    </div>
  )
}

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-20 flex h-dvh w-[220px] shrink-0 flex-col border-r-[0.5px] border-[#E5E5E5] bg-white">
      <div className="flex flex-1 flex-col overflow-y-auto px-3 pb-3 pt-5">
        <div className="mb-6 flex items-start gap-2 px-1">
          <div className="relative h-9 w-9 shrink-0">
            <span className="absolute left-0 top-1 h-7 w-7 rounded-full bg-[#4A7C7E] opacity-90" />
            <span className="absolute left-3 top-0 h-7 w-7 rounded-full bg-[#6BADA8] opacity-95" />
          </div>
          <div className="min-w-0 pt-0.5">
            <div className="text-[15px] font-bold leading-tight text-[#1a1a1a]">
              CONQR.AI
            </div>
            <div className="mt-0.5 text-[9px] font-medium uppercase tracking-[0.08em] text-[#888]">
              Lawyer goes virtual
            </div>
          </div>
        </div>

        <nav className="flex flex-col gap-3 text-[13px]">
          <Section title="Home">
            <NavRow item={{ label: 'Dashboard', active: true }} />
            <NavRow item={{ label: 'Payments' }} />
            <NavRow item={{ label: 'All Documents' }} />
            <NavRow item={{ label: 'Business View', locked: true }} />
            <NavRow item={{ label: 'Draft Document' }} />
          </Section>

          <Section title="Analysis & Compliance">
            <NavRow item={{ label: 'Compliance', locked: true }} />
            <NavRow item={{ label: 'Conqr Connect' }} />
            <NavRow item={{ label: 'Conflict Check' }} />
            <NavRow item={{ label: 'Review and Check' }} />
            <NavRow item={{ label: 'Gap Analysis' }} />
          </Section>

          <Section title="Team & Business" lockedHeader />

          <Section title="Tools & Libraries">
            <NavRow item={{ label: 'Clauses and Templates' }} />
            <NavRow item={{ label: 'Proof Read' }} />
            <NavRow item={{ label: 'Chat', locked: true }} />
          </Section>

          <Section title="Support Center">
            <NavRow item={{ label: 'Policies' }} />
            <NavRow item={{ label: 'Settings' }} />
            <NavRow item={{ label: 'Help' }} />
          </Section>
        </nav>
      </div>

      <div className="mt-auto flex items-center gap-2 border-t-[0.5px] border-[#E5E5E5] px-3 py-3">
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#4A7C7E] text-[13px] font-medium text-white"
          aria-hidden
        >
          F
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-bold text-[#1a1a1a]">
            Company Name
          </div>
          <div className="text-[11px] text-[#888]">India</div>
        </div>
        <button
          type="button"
          className="shrink-0 text-[12px] text-[#888] hover:text-[#666]"
          aria-label="Collapse sidebar"
        >
          ◄
        </button>
      </div>
    </aside>
  )
}
