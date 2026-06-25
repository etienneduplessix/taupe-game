<template>
  <div class="relative min-h-screen scanlines overflow-hidden">
    <Scene />

    <div class="relative z-10 p-4 md:p-8">
      <!-- Header -->
      <header class="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
        <div class="flex items-center gap-4">
          <NuxtLink to="/" class="btn-3d btn-secondary !py-2 !px-4">
            <span class="text-xl">🏠</span>
            Lobby
          </NuxtLink>
          <h1 class="title-3d text-3xl md:text-5xl">ADMIN</h1>
        </div>
        <div class="flex gap-3">
          <NuxtLink to="/admin/stats" class="btn-3d btn-secondary !py-2 !px-4">
            <span class="text-xl">📊</span>
            Live Stats
          </NuxtLink>
          <button @click="showCreateModal = true" class="btn-3d btn-primary !py-2 !px-4">
            <span class="text-xl">➕</span>
            New Session
          </button>
        </div>
      </header>

      <!-- Sessions Grid -->
      <div v-if="loading" class="text-center py-20">
        <p class="font-arcade text-amber-200 animate-pulse">LOADING SESSIONS...</p>
      </div>

      <div v-else-if="sessions.length === 0" class="panel-3d p-10 max-w-xl mx-auto text-center">
        <div class="text-6xl mb-4">🎮</div>
        <p class="font-display text-xl text-purple-100 mb-4">No sessions yet.</p>
        <p class="font-arcade text-[10px] text-purple-300/70 mb-6">Create your first game session!</p>
        <button @click="showCreateModal = true" class="btn-3d btn-primary">
          <span class="text-xl">➕</span>
          Create Session
        </button>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 max-w-7xl mx-auto">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="panel-3d p-5 flex flex-col gap-3"
        >
          <div class="flex justify-between items-start gap-2">
            <h3 class="font-display font-bold text-xl text-amber-100 leading-tight">{{ session.name }}</h3>
            <span :class="statusBadgeClass(session.status)" class="font-arcade text-[9px] px-2 py-1 rounded-md uppercase whitespace-nowrap">
              {{ session.status }}
            </span>
          </div>

          <div class="font-arcade text-[9px] text-amber-300 uppercase tracking-widest">
            {{ gameTypeLabel(session) }}
          </div>

          <div v-if="gameTypeOf(session) === 'taupe'" class="flex flex-wrap gap-2 text-[10px] font-arcade text-purple-200/80">
            <div class="chip-sm">
              <span>⚡</span>
              <span>{{ session.config_json?.base_spawn_interval_ms || '-' }}ms</span>
            </div>
            <div class="chip-sm">
              <span>⏱️</span>
              <span>{{ session.config_json?.base_timeout_ms || '-' }}ms</span>
            </div>
            <div class="chip-sm">
              <span>💔</span>
              <span>{{ session.config_json?.max_mistakes || '-' }} miss</span>
            </div>
          </div>
          <div v-else-if="gameTypeOf(session) === 'dot_rush'" class="flex flex-wrap gap-2 text-[10px] font-arcade text-purple-200/80">
            <div class="chip-sm">
              <span>⏱️</span>
              <span>{{ session.config_json?.initial_lifetime_ms || '-' }}ms</span>
            </div>
            <div class="chip-sm">
              <span>🟡</span>
              <span>{{ session.config_json?.initial_radius_pct || '-' }}%</span>
            </div>
            <div class="chip-sm">
              <span>💔</span>
              <span>{{ session.config_json?.max_misses || '-' }} miss</span>
            </div>
          </div>
          <div v-else-if="gameTypeOf(session) === 'among_us'" class="flex flex-wrap gap-2 text-[10px] font-arcade text-purple-200/80">
            <div class="chip-sm">
              <span>🕵️</span>
              <span>{{ session.config_json?.impostor_count || 1 }} impostor(s)</span>
            </div>
            <div class="chip-sm">
              <span>🔪</span>
              <span>{{ session.config_json?.kill_cooldown_seconds || '-' }}s cooldown</span>
            </div>
            <div class="chip-sm">
              <span>📋</span>
              <span>{{ session.config_json?.tasks_per_crewmate || '-' }} tasks</span>
            </div>
          </div>

          <div class="flex flex-wrap gap-2 mt-2">
            <button
              v-if="session.status === 'waiting'"
              @click="startSession(session.id)"
              class="btn-3d btn-primary !text-[10px] !py-2 !px-3 flex-1"
            >
              <span>▶️</span> START · {{ session.queue_count || 0 }} 👥
            </button>
            <button
              v-if="session.status === 'running'"
              @click="endSession(session.id)"
              class="btn-3d btn-danger !text-[10px] !py-2 !px-3 flex-1"
            >
              <span>⏹️</span> END
            </button>
            <NuxtLink
              :to="`/admin/edit/${session.id}`"
              class="btn-3d btn-secondary !text-[10px] !py-2 !px-3"
            >
              <span>⚙️</span> EDIT
            </NuxtLink>
            <button
              @click="deleteSession(session.id)"
              class="btn-3d btn-danger !text-[10px] !py-2 !px-3"
              title="Delete session"
            >
              🗑️
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <Transition name="fade">
      <div v-if="showCreateModal" class="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
        <div class="panel-3d p-8 max-w-md w-full">
          <h2 class="title-3d text-3xl mb-6 text-center">NEW SESSION</h2>
          <form @submit.prevent="createSession" class="flex flex-col gap-4">
            <div>
              <label class="font-arcade text-[10px] text-amber-300 block mb-2">SESSION NAME</label>
              <input
                v-model="newSessionName"
                type="text"
                class="w-full p-3 bg-[#1a0f08] text-amber-100 border-2 border-amber-400/60 rounded-lg font-display focus:border-amber-400 focus:outline-none"
                placeholder="Finals 2026"
                required
                autofocus
              />
            </div>
            <div>
              <label class="font-arcade text-[10px] text-amber-300 block mb-2">GAME TYPE</label>
              <div class="flex gap-2">
                <button
                  type="button"
                  @click="newSessionGameType = 'taupe'"
                  :class="['btn-3d', 'flex-1', '!py-2', '!text-xs', newSessionGameType === 'taupe' ? 'btn-primary' : 'btn-ghost']"
                >
                  🐹 Taupe Typing
                </button>
              <button
                  type="button"
                  @click="newSessionGameType = 'dot_rush'"
                  :class="['btn-3d', 'flex-1', '!py-2', '!text-xs', newSessionGameType === 'dot_rush' ? 'btn-primary' : 'btn-ghost']"
                >
                  🟡 Dot Rush
                </button>
                <button
                  type="button"
                  @click="newSessionGameType = 'among_us'"
                  :class="['btn-3d', 'flex-1', '!py-2', '!text-xs', newSessionGameType === 'among_us' ? 'btn-primary' : 'btn-ghost']"
                >
                  🕵️ Among Us
                </button>
              </div>
            </div>
            <div class="flex justify-end gap-3 mt-2">
              <button type="button" @click="showCreateModal = false" class="btn-3d btn-secondary !py-2 !px-4">
                Cancel
              </button>
              <button type="submit" class="btn-3d btn-primary !py-2 !px-4">
                <span>✨</span>
                Create
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import Scene from '~/components/Scene.vue'

definePageMeta({ middleware: 'admin' })

const config = useRuntimeConfig()
const API = config.public.apiBase

const sessions = ref([])
const loading = ref(true)
const showCreateModal = ref(false)
const newSessionName = ref('')
const newSessionGameType = ref('taupe')

const DOT_RUSH_DEFAULTS = {
  game_type: 'dot_rush',
  max_misses: 3,
  initial_lifetime_ms: 1500,
  min_lifetime_ms: 400,
  initial_radius_pct: 8,
  min_radius_pct: 2.5,
  inter_round_gap_ms: 600,
  scaling_exponent: 1,
  miss_penalty: -5,
  countdown_seconds: 5,
}

const AMONG_US_DEFAULTS = {
  game_type: 'among_us',
  impostor_count: 1,
  kill_cooldown_seconds: 25,
  kill_range: 1.5,
  report_range: 1.0,
  discussion_duration_seconds: 30,
  voting_duration_seconds: 15,
  tasks_per_crewmate: 4,
  countdown_seconds: 5,
}

function gameTypeOf(s) {
  return s.game_type || s.config_json?.game_type || 'taupe'
}
function gameTypeLabel(s) {
  const gt = gameTypeOf(s)
  if (gt === 'dot_rush') return '🟡 Dot Rush'
  if (gt === 'among_us') return '🕵️ Among Us'
  return '🐹 Taupe Typing'
}

const fetchSessions = async () => {
  try {
    const data = await $fetch(`${API}/admin/sessions`, { credentials: 'include' })
    sessions.value = data
  } catch (e) {
    console.error('Failed to fetch sessions', e)
  } finally {
    loading.value = false
  }
}

const createSession = async () => {
  if (!newSessionName.value.trim()) return
  try {
    const body = { name: newSessionName.value.trim() }
    if (newSessionGameType.value === 'dot_rush') {
      body.config = { ...DOT_RUSH_DEFAULTS }
    } else if (newSessionGameType.value === 'among_us') {
      body.config = { ...AMONG_US_DEFAULTS }
    }
    await $fetch(`${API}/admin/sessions`, {
      method: 'POST',
      credentials: 'include',
      body,
    })
    showCreateModal.value = false
    newSessionName.value = ''
    newSessionGameType.value = 'taupe'
    await fetchSessions()
  } catch (e) {
    alert('Error creating session: ' + (e.data?.detail || e.message))
  }
}

const startSession = async (id) => {
  try {
    await $fetch(`${API}/admin/sessions/${id}/start`, { method: 'POST', credentials: 'include' })
    await fetchSessions()
  } catch (e) {
    alert('Error starting session')
  }
}

const endSession = async (id) => {
  try {
    await $fetch(`${API}/admin/sessions/${id}/end`, { method: 'POST', credentials: 'include' })
    await fetchSessions()
  } catch (e) {
    alert('Error ending session')
  }
}

const deleteSession = async (id) => {
  if (!confirm('Delete this session? This cannot be undone.')) return
  try {
    await $fetch(`${API}/admin/sessions/${id}`, { method: 'DELETE', credentials: 'include' })
    await fetchSessions()
  } catch (e) {
    alert('Error deleting session')
  }
}

const statusBadgeClass = (status) => ({
  'waiting': 'bg-yellow-500/30 text-yellow-200 border-2 border-yellow-400/60',
  'running': 'bg-green-500/30 text-green-200 border-2 border-green-400/60 animate-pulse',
  'ended': 'bg-gray-500/30 text-gray-200 border-2 border-gray-400/40',
}[status] || 'bg-gray-500/30 text-gray-200')

let pollInterval = null
onMounted(() => {
  fetchSessions()
  pollInterval = setInterval(fetchSessions, 2000)
})
onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.chip-sm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: rgba(26, 15, 8, 0.6);
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 6px;
}
.fade-enter-active, .fade-leave-active { transition: opacity 200ms; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
