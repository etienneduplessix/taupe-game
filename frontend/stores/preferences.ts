import { defineStore } from 'pinia'

const STORAGE_KEY = 'taupe.layout'
const VALID_LAYOUTS = ['QWERTY', 'AZERTY', 'NUMPAD'] as const
type Layout = typeof VALID_LAYOUTS[number]

export const usePreferencesStore = defineStore('preferences', {
  state: () => ({
    layout: 'QWERTY' as Layout,
    hydrated: false,
  }),
  actions: {
    hydrate() {
      if (this.hydrated || !import.meta.client) return
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved && (VALID_LAYOUTS as readonly string[]).includes(saved)) {
        this.layout = saved as Layout
      }
      this.hydrated = true
    },
    setLayout(l: Layout) {
      this.layout = l
      if (import.meta.client) localStorage.setItem(STORAGE_KEY, l)
    },
  },
})
