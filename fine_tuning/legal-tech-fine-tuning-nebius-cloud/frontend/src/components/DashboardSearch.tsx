/** Top-of-page search matching the dashboard spec; focuses Shivay input on click. */
export function DashboardSearch() {
  return (
    <div className="mx-auto mb-8 w-full max-w-[600px]">
      <button
        type="button"
        onClick={() => document.getElementById('shivay-input')?.focus()}
        className="flex h-10 w-full items-center gap-2 rounded-lg border-[0.5px] border-[#ddd] bg-white px-3 text-left transition hover:bg-[#fafafa]"
      >
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
        <span className="flex-1 text-[15px] text-[#aaa]">Search for anything</span>
        <kbd className="shrink-0 rounded border-[0.5px] border-[#ddd] bg-[#fafafa] px-1.5 py-0.5 text-[11px] text-[#888]">
          ⌘K
        </kbd>
      </button>
    </div>
  )
}
