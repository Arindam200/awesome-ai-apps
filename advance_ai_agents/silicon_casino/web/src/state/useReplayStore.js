import { create } from 'zustand'

export const useReplayStore = create((set) => ({
  index: 0,
  playing: false,
  speed: 1,
  handNavOpen: true,
  selectedHandId: '',
  stateOverride: null,
  setIndex: (indexOrUpdater) =>
    set((s) => ({
      index: typeof indexOrUpdater === 'function' ? indexOrUpdater(s.index) : indexOrUpdater
    })),
  play: () => set({ playing: true }),
  pause: () => set({ playing: false }),
  togglePlay: () => set((s) => ({ playing: !s.playing })),
  setSpeed: (speed) => set({ speed }),
  toggleHandNav: () => set((s) => ({ handNavOpen: !s.handNavOpen })),
  setSelectedHand: (selectedHandId) => set({ selectedHandId }),
  setStateOverride: (stateOverride) => set({ stateOverride }),
  resetReplayState: () =>
    set({
      index: 0,
      playing: false,
      speed: 1,
      handNavOpen: true,
      selectedHandId: '',
      stateOverride: null
    })
}))
