export function Topbar() {
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b-[0.5px] border-[#E5E5E5] bg-white px-6">
      <nav className="text-[13px] text-[#888]" aria-label="Breadcrumb">
        <span>Home</span>
        <span className="mx-1.5 text-[#888]">›</span>
        <span>All Documents</span>
      </nav>

      <div className="flex items-center gap-3">
        <div
          className="flex h-[34px] min-w-[34px] items-center justify-center rounded-full border border-[#ddd] bg-[#f0f0f0] px-2 text-[12px] text-[#555]"
          title="Notifications"
        >
          423
        </div>

        <div
          className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-[#4A7C7E] text-[13px] font-medium text-white"
          aria-hidden
        >
          F
        </div>

        <div className="hidden text-left sm:block">
          <div className="text-[13px] font-medium text-[#1a1a1a]">User Name</div>
          <div className="text-[11px] text-[#888]">user.email@smth.com</div>
        </div>

        <button
          type="button"
          className="p-1 text-[18px] leading-none text-[#888] hover:text-[#666]"
          aria-label="More options"
        >
          ···
        </button>
      </div>
    </header>
  )
}
