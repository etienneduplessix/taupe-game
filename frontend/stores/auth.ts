import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    isAuthenticated: false,
  }),
  actions: {
    setUser(userData) {
      this.user = userData
      this.isAuthenticated = !!userData
    },
    logout() {
      this.user = null
      this.isAuthenticated = false
    }
  }
})
