<template>
  <div class="relative min-h-screen scanlines">
    <Scene />

    <!-- Peeking moles from holes at bottom -->
    <div class="absolute bottom-[12%] left-[10%] pointer-events-none">
      <div class="text-5xl animate-mole-bob drop-shadow-[0_6px_8px_rgba(0,0,0,0.6)]">🐹</div>
    </div>
    <div class="absolute bottom-[14%] right-[15%] pointer-events-none">
      <div class="text-6xl animate-mole-bob drop-shadow-[0_6px_8px_rgba(0,0,0,0.6)]" style="animation-delay: -0.3s;">🐹</div>
    </div>
    <div class="absolute bottom-[10%] left-[45%] pointer-events-none">
      <div class="text-4xl animate-mole-bob drop-shadow-[0_6px_8px_rgba(0,0,0,0.6)]" style="animation-delay: -0.6s;">🐹</div>
    </div>

    <!-- Content -->
    <div class="relative z-10 flex flex-col items-center justify-center min-h-screen p-6">
      <div class="text-center mb-10 animate-float">
        <h1 class="title-3d text-6xl md:text-8xl mb-3">TAUPE TYPING</h1>
        <p class="font-arcade text-[10px] md:text-xs text-amber-200/80 tracking-[0.4em] mt-4">
          WHACK · TYPE · SURVIVE
        </p>
      </div>

      <div v-if="user" class="panel-3d p-12 max-w-lg w-full">
        <div class="flex items-center gap-4 mb-6 pb-6 border-b border-amber-500/20">
          <div class="relative">
            <img v-if="user.avatar_url" :src="user.avatar_url" class="w-16 h-16 rounded-full border-4 border-amber-400 shadow-lg" />
            <div v-else class="w-16 h-16 rounded-full bg-gradient-to-br from-amber-400 to-amber-700 flex items-center justify-center text-3xl shadow-lg border-4 border-amber-400">🐹</div>
            <div class="absolute -bottom-1 -right-1 w-5 h-5 bg-green-400 border-2 border-[#1b1042] rounded-full shadow-md"></div>
          </div>
          <div class="flex-1">
            <div class="text-[10px] text-amber-300 uppercase tracking-widest font-bold">Player</div>
            <div class="text-2xl font-display text-white">{{ user.display_name }}</div>
            <div class="text-sm text-purple-300">@{{ user.login }}</div>
          </div>
          <div v-if="user.is_admin" class="font-arcade text-[9px] bg-gradient-to-b from-purple-400 to-purple-700 text-white px-3 py-2 rounded-lg shadow-[0_4px_0_#4c1d95]">
            ADMIN
          </div>
        </div>

        <div class="flex flex-col gap-4">
          <div v-if="loadingSessions" class="font-arcade text-[10px] text-amber-300 text-center py-4 animate-pulse">
            LOADING GAMES...
          </div>
          <div v-else-if="runningSessions.length === 0" class="panel-3d p-5 text-center">
            <div class="text-4xl mb-2">💤</div>
            <div class="font-arcade text-[10px] text-amber-300">NO OPEN GAMES</div>
            <div class="text-xs text-purple-200/70 mt-1 font-display">Ask an admin to create one!</div>
          </div>
          <div v-else class="flex flex-col gap-2">
            <div class="font-arcade text-[10px] text-amber-300 mb-1">PICK A GAME</div>
            <NuxtLink
              v-for="s in runningSessions"
              :key="s.id"
              :to="`/play?sessionId=${s.id}`"
              :class="['btn-3d', '!py-3', 'flex', 'items-center', 'justify-between', s.status === 'running' ? 'btn-success' : 'btn-primary']"
            >
              <span class="flex items-center gap-2">
                <span class="text-xl">{{ s.status === 'running' ? '⚡' : '⏳' }}</span>
                <span>{{ s.name }}</span>
                <span v-if="s.status === 'waiting'" class="font-arcade text-[8px] text-white/70">· {{ s.queue_count }} 👥 QUEUED</span>
              </span>
              <span class="font-arcade text-[9px] text-white/80">
                {{ s.status === 'running' ? 'JOIN →' : 'QUEUE →' }}
              </span>
            </NuxtLink>
          </div>
          <NuxtLink v-if="user.is_admin" to="/admin" class="btn-3d btn-admin">
            <span class="text-2xl">🎛️</span>
            Admin Panel
          </NuxtLink>
          <button @click="logout" class="btn-3d btn-ghost self-center mt-1">
            Logout
          </button>
        </div>
      </div>

      <div v-else class="panel-3d p-8 text-center">
        <div class="text-4xl animate-mole-bob inline-block">🐹</div>
        <p class="text-gray-300 mt-4 font-display">Loading...</p>
      </div>

      <div class="mt-20 px-8 py-6 text-center max-w-md animate-flash-white">
        <div class="font-arcade text-[9px] mb-3 tracking-widest">HOW TO PLAY</div>
        <p class="text-xs font-display leading-relaxed">
          A taupe pops out with a letter. Smash that key fast.<br/>
          Miss too many or be too slow? You're out.<br/>
          <span class="font-semibold">Last player alive wins.</span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useAuthStore } from '~/stores/auth'
import Scene from '~/components/Scene.vue'

const authStore = useAuthStore()
const user = computed(() => authStore.user)
const runningSessions = ref([])
const loadingSessions = ref(true)

async function fetchSessions() {
  loadingSessions.value = true
  try {
    const data = await $fetch('/api/sessions', { credentials: 'include' })
    runningSessions.value = data
  } catch (e) {
    runningSessions.value = []
  } finally {
    loadingSessions.value = false
  }
}

let pollInterval = null
onUnmounted(() => { if (pollInterval) clearInterval(pollInterval) })

onMounted(async () => {
  try {
    const userData = await $fetch('/api/me')
    if (userData) {
      authStore.setUser(userData)
      fetchSessions()
      pollInterval = setInterval(fetchSessions, 2000)
    }
    else navigateTo('/login')
  } catch (e) { navigateTo('/login') }
})

async function logout() {
  try { await $fetch('/api/auth/logout', { method: 'POST' }) } catch (e) {}
  authStore.setUser(null)
  navigateTo('/login')
}
</script>

<style scoped>
.animate-flash-white,
.animate-flash-white * {
  color: #ffffff !important;
}
.animate-flash-white {
  animation: flash-white 1.4s ease-in-out infinite;
}
@keyframes flash-white {
  0%, 100% { opacity: 0.55; text-shadow: none; }
  50%      { opacity: 1; text-shadow: 0 0 10px rgba(255,255,255,0.85), 0 0 22px rgba(255,255,255,0.45); }
}
</style>
