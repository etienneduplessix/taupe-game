<template>
  <div class="relative min-h-screen scanlines overflow-hidden">
    <Scene />

    <div class="relative z-10 p-4 md:p-8">
      <!-- Header -->
      <header class="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
        <div class="flex items-center gap-4">
          <NuxtLink to="/admin" class="btn-3d btn-secondary !py-2 !px-4">
            <span class="text-xl">←</span>
            Sessions
          </NuxtLink>
          <h1 class="title-3d text-3xl md:text-5xl">LIVE STATS</h1>
        </div>
        <div v-if="polling && stats && !error" class="chip">
          <div class="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
          <div class="font-arcade text-[10px] text-green-300">LIVE</div>
        </div>
      </header>

      <!-- Session picker -->
      <div v-if="!route.query.sessionId" class="panel-3d p-8 max-w-2xl mx-auto">
        <h2 class="font-display text-2xl text-amber-100 mb-4">Pick a running session</h2>
        <div v-if="runningSessions.length === 0" class="text-purple-200/70 font-arcade text-xs">
          No running sessions. Start one from the admin panel.
        </div>
        <div v-else class="flex flex-col gap-2">
          <NuxtLink
            v-for="s in runningSessions"
            :key="s.id"
            :to="`/admin/stats?sessionId=${s.id}`"
            class="panel-3d p-4 flex justify-between items-center hover:brightness-110 transition"
          >
            <span class="font-display text-lg text-amber-100">{{ s.name }}</span>
            <span class="font-arcade text-[9px] text-green-300 animate-pulse">● RUNNING</span>
          </NuxtLink>
        </div>
      </div>

      <div v-else-if="error" class="panel-3d p-8 max-w-xl mx-auto text-center">
        <div class="text-5xl mb-3">⚠️</div>
        <p class="font-display text-red-300">{{ error }}</p>
      </div>

      <div v-else-if="stats" class="grid grid-cols-1 lg:grid-cols-3 gap-5 max-w-7xl mx-auto">
        <!-- Metrics -->
        <div class="lg:col-span-1 flex flex-col gap-4">
          <div class="panel-3d p-5">
            <div class="font-arcade text-[10px] text-amber-300 mb-2">PLAYERS ALIVE</div>
            <div class="font-arcade text-5xl text-red-300">{{ stats.alive_count }}</div>
          </div>
          <div class="panel-3d p-5">
            <div class="font-arcade text-[10px] text-amber-300 mb-2">CURRENT ROUND</div>
            <div class="font-arcade text-5xl text-yellow-300">{{ String(stats.current_round).padStart(3, '0') }}</div>
          </div>
          <div class="panel-3d p-5">
            <div class="font-arcade text-[10px] text-amber-300 mb-2">SPAWN INTERVAL</div>
            <div class="font-display text-3xl text-amber-100 font-bold">{{ stats.current_interval }}ms</div>
          </div>
          <div class="panel-3d p-5">
            <div class="font-arcade text-[10px] text-amber-300 mb-2">TAUPE TIMEOUT</div>
            <div class="font-display text-3xl text-amber-100 font-bold">{{ stats.current_timeout }}ms</div>
          </div>

          <!-- Coalition leaderboard -->
          <div class="panel-3d p-5">
            <h2 class="title-3d text-xl mb-3">⚔️ COALITIONS</h2>
            <div v-if="!stats.coalitions_ranking || stats.coalitions_ranking.length === 0" class="text-center py-4 font-arcade text-[9px] text-purple-200/60">
              NO COALITION DATA
            </div>
            <div v-else class="flex flex-col gap-2">
              <div
                v-for="(c, i) in stats.coalitions_ranking"
                :key="c.id"
                class="flex items-center gap-3 p-2 bg-[#1a0f08]/60 border rounded-lg"
                :style="{ borderColor: (c.color || '#fcd34d') + '99' }"
              >
                <div class="font-arcade text-lg w-7" :class="rankColor(i)">#{{ i + 1 }}</div>
                <img v-if="c.image_url" :src="c.image_url" class="w-8 h-8 object-contain" />
                <div class="flex-1 min-w-0">
                  <div class="font-display font-bold truncate" :style="{ color: c.color || '#fcd34d' }">{{ c.name }}</div>
                  <div class="font-arcade text-[8px] text-amber-300/70">{{ c.player_count }} player{{ c.player_count === 1 ? '' : 's' }}</div>
                </div>
                <div class="font-arcade text-lg text-yellow-300">{{ String(c.score).padStart(5, '0') }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Leaderboard -->
        <div class="lg:col-span-2 panel-3d p-5">
          <h2 class="title-3d text-2xl mb-4">🏆 LEADERBOARD <span class="font-arcade text-[10px] text-amber-300/70 align-middle">({{ stats.top_scores?.length || 0 }})</span></h2>
          <div v-if="!stats.top_scores || stats.top_scores.length === 0" class="text-center py-10 font-arcade text-[10px] text-purple-200/60">
            NO PLAYERS YET...
          </div>
          <div v-else class="flex flex-col gap-2">
            <div
              v-for="(entry, i) in stats.top_scores"
              :key="entry.user_id || i"
              class="flex items-center gap-3 p-3 bg-[#1a0f08]/60 border rounded-lg"
              :class="entry.eliminated ? 'opacity-50' : ''"
              :style="entry.coalition ? { borderColor: (entry.coalition.color || '#fcd34d') + '66' } : { borderColor: 'rgba(251, 191, 36, 0.2)' }"
            >
              <div class="font-arcade text-xl w-10" :class="rankColor(i)">#{{ i + 1 }}</div>
              <img
                v-if="entry.coalition && entry.coalition.image_url"
                :src="entry.coalition.image_url"
                :title="entry.coalition.name"
                class="w-8 h-8 object-contain shrink-0"
              />
              <div class="flex-1 min-w-0">
                <div class="font-display font-bold text-amber-100 truncate">{{ entry.display_name }}</div>
                <div class="font-arcade text-[8px] truncate flex items-center gap-2">
                  <span class="text-amber-300/70">@{{ entry.login }}</span>
                  <span v-if="entry.coalition" :style="{ color: entry.coalition.color || '#fcd34d' }">
                    · {{ entry.coalition.name }}
                  </span>
                </div>
              </div>
              <div v-if="entry.eliminated" class="font-arcade text-[8px] text-red-300">OUT</div>
              <div class="font-arcade text-xl text-yellow-300">{{ String(entry.score).padStart(5, '0') }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import Scene from '~/components/Scene.vue'

definePageMeta({ middleware: 'admin' })

const config = useRuntimeConfig()
const API = config.public.apiBase
const route = useRoute()

const stats = ref(null)
const error = ref(null)
const polling = ref(false)
const runningSessions = ref([])
let pollInterval = null

const fetchSessions = async () => {
  try {
    const data = await $fetch(`${API}/admin/sessions`, { credentials: 'include' })
    runningSessions.value = data.filter(s => s.status === 'running')
  } catch (e) {
    console.error(e)
  }
}

const fetchStats = async () => {
  const sessionId = route.query.sessionId
  if (!sessionId) return
  try {
    const data = await $fetch(`${API}/admin/sessions/${sessionId}/stats`, { credentials: 'include' })
    if (data.error) {
      error.value = data.error
      stats.value = null
    } else {
      stats.value = data
      error.value = null
    }
  } catch (e) {
    error.value = 'Failed to fetch live stats'
  }
}

const rankColor = (i) => {
  if (i === 0) return 'text-yellow-300'
  if (i === 1) return 'text-gray-300'
  if (i === 2) return 'text-amber-600'
  return 'text-purple-200/70'
}

onMounted(() => {
  fetchSessions()
  fetchStats()
  polling.value = true
  pollInterval = setInterval(fetchStats, 2000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>
