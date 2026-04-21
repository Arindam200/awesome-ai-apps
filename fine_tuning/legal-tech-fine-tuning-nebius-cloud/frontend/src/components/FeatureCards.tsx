const CARDS = [
  {
    title: 'Conqr Connect',
    subtitle: 'Link and sync related legal docs for easy reference.',
    icon: 'link',
  },
  {
    title: 'Conflict Check',
    subtitle: 'Catch grammatical errors and inconsistencies',
    icon: 'scales',
  },
  {
    title: 'Proof-Read',
    subtitle: 'Catch grammatical errors and inconsistencies',
    icon: 'acheck',
  },
  {
    title: 'Gap Analysis',
    subtitle: 'Catch grammatical errors and inconsistencies',
    icon: 'chart',
  },
  {
    title: 'Review and Check',
    subtitle: 'Catch grammatical errors and inconsistencies',
    icon: 'doc',
  },
  {
    title: 'Manage Files',
    subtitle: 'Catch grammatical errors and inconsistencies',
    icon: 'files',
  },
] as const

function CardIcon({ name }: { name: (typeof CARDS)[number]['icon'] }) {
  const stroke = 2
  const common = {
    fill: 'none' as const,
    stroke: 'white',
    strokeWidth: stroke,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }
  return (
    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#6BADA8]">
      <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden>
        {name === 'link' && (
          <>
            <rect {...common} x="3" y="7" width="8" height="10" rx="1" />
            <rect {...common} x="13" y="7" width="8" height="10" rx="1" />
            <path {...common} d="M11 12h2" />
          </>
        )}
        {name === 'scales' && (
          <>
            <path {...common} d="M12 3v18" />
            <path {...common} d="M5 8l7-3 7 3" />
            <path {...common} d="M7 8v6l5 2 5-2V8" />
          </>
        )}
        {name === 'acheck' && (
          <>
            <path {...common} d="M7 8h8v10H7z" />
            <path {...common} d="M10 12l2 2 4-4" />
          </>
        )}
        {name === 'chart' && (
          <>
            <path {...common} d="M4 19V5" />
            <path {...common} d="M4 19h16" />
            <path {...common} d="M8 15v-4" />
            <path {...common} d="M12 15V9" />
            <path {...common} d="M16 15v-6" />
          </>
        )}
        {name === 'doc' && (
          <>
            <path {...common} d="M7 4h7l3 3v13H7z" />
            <path {...common} d="M9 9h6M9 13h6M9 17h4" />
          </>
        )}
        {name === 'files' && (
          <>
            <path {...common} d="M6 6h8v14H6z" />
            <path {...common} d="M9 4h8v14" />
          </>
        )}
      </svg>
    </div>
  )
}

export function FeatureCards() {
  return (
    <div className="mx-auto grid max-w-[720px] grid-cols-1 gap-4 sm:grid-cols-3">
      {CARDS.map((c) => (
        <button
          key={c.title}
          type="button"
          className="flex flex-col rounded-[10px] border-0 bg-[#EEF4F4] p-5 text-left transition-colors hover:cursor-pointer hover:bg-[#E0ECEC]"
        >
          <CardIcon name={c.icon} />
          <div className="mt-3 text-[14px] font-medium text-[#1a1a1a]">
            {c.title}
          </div>
          <p className="mt-1 text-[12px] leading-[1.4] text-[#888]">
            {c.subtitle}
          </p>
        </button>
      ))}
    </div>
  )
}
