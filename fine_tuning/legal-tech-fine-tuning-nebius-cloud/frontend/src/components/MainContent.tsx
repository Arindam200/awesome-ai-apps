import { Chat } from './Chat'
import { DashboardSearch } from './DashboardSearch'
import { FeatureCards } from './FeatureCards'

export function MainContent() {
  return (
    <main className="min-h-0 flex-1 overflow-y-auto bg-[#F5F0EA] px-10 pb-10 pt-12">
      <div className="mx-auto mb-8 max-w-4xl text-center">
        <p className="text-[15px] font-normal text-[#4A7C7E]">Hey, Name</p>
        <h2 className="mt-1 text-[26px] font-semibold leading-tight text-[#1a1a1a]">
          What do you need to do today?
        </h2>
      </div>

      <DashboardSearch />

      <div className="mb-10">
        <FeatureCards />
      </div>

      <div className="mx-auto max-w-3xl">
        <h3 className="mb-3 text-center text-[14px] font-medium text-[#1a1a1a]">
          Shivay
        </h3>
        <div className="flex max-h-[min(420px,50vh)] min-h-[280px] flex-col overflow-hidden rounded-lg border-[0.5px] border-[#E5E5E5] bg-white">
          <Chat />
        </div>

        <div className="mt-8 flex justify-center">
          <img
            src="https://cdn.asp.events/CLIENT_Informa__AADDE28D_5056_B739_5481D63BF875B0DF/sites/london-tech-week-2024/media/libraries/exhibitor-list/NEBIUS-B-clearspace-Logo.png/fit-in/500x9999/filters:no_upscale()"
            alt="Nebius AI"
            className="h-auto max-h-14 w-auto max-w-[220px] object-contain"
            loading="lazy"
            decoding="async"
          />
        </div>
      </div>
    </main>
  )
}
