<template>
  <div class="relative min-h-screen scanlines">
    <Scene />

    <!-- Game-specific arena -->
    <component
      :is="arenaComponent"
      v-if="arenaComponent"
      :socket="socket"
      :session-id="selectedSessionId"
      :game-started="gameStarted"
      :queue-count="queueCount"
      :alive-count="aliveCount"
      :layout="layout"
      @session-running="sessionStatus = 'running'"
    />

    <!-- Chat sidebar -->
    <div
      class="panel-3d p-3 flex-col"
      style="position: fixed; right: 12px; top: 12px; z-index: 40; width: 220px; height: calc(100vh - 24px); display: flex;"
    >
      <div class="font-arcade text-[10px] text-amber-300 px-1 pb-2 border-b border-amber-400/20 mb-2 flex items-center gap-2 shrink-0">
        💬 CHAT
      </div>
      <div ref="chatListEl" class="flex-1 overflow-y-auto pr-1 flex flex-col gap-2 text-sm" style="min-height: 0;">
        <div v-if="chatMessages.length === 0" class="font-arcade text-[9px] text-purple-200/50 text-center py-6">
          NO MESSAGES YET
        </div>
        <div v-for="(m, i) in chatMessages" :key="i" class="flex flex-col">
          <div class="font-arcade text-[9px] text-amber-300">{{ m.display_name }}</div>
          <div class="font-display text-amber-100 bg-[#1a0f08]/60 border border-amber-400/20 rounded-lg px-2 py-1 break-words">
            {{ m.text }}
          </div>
        </div>
      </div>
      <form @submit.prevent="sendChat" class="flex gap-2 mt-2 shrink-0">
        <input
          v-model="chatInput"
          type="text"
          maxlength="300"
          placeholder="Say something..."
          class="flex-1 min-w-0 px-2 py-1 bg-[#1a0f08] text-amber-100 border-2 border-amber-400/40 rounded-lg font-display text-sm focus:border-amber-400 focus:outline-none"
        />
        <button type="submit" class="btn-3d btn-primary !py-1 !px-3 !text-xs">SEND</button>
      </form>
    </div>

    <!-- Pre-game countdown -->
    <Transition name="fade">
      <div
        v-if="countdownValue !== null"
        class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-40 pointer-events-none"
      >
        <div
          :key="countdownValue"
          class="font-arcade animate-countdown-pop drop-shadow-[0_8px_24px_rgba(250,204,21,0.6)]"
          :class="countdownValue === 0 ? 'text-green-300' : 'text-yellow-300'"
          style="font-size: clamp(8rem, 22vw, 18rem); line-height: 1;"
        >
          {{ countdownValue === 0 ? 'GO!' : countdownValue }}
        </div>
      </div>
    </Transition>

    <!-- Eliminated overlay -->
    <Transition name="fade">
      <div v-if="isEliminated && !isWinner" class="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 scanlines">
        <div class="panel-3d p-10 text-center max-w-lg w-full mx-4" style="border-color: rgba(239,68,68,0.6);">
          <div class="text-8xl mb-4 animate-float">☠️</div>
          <h2 class="title-3d text-5xl md:text-6xl mb-4" style="color: #fca5a5;">ELIMINATED</h2>
          <p class="text-purple-200 mb-2 font-display">{{ eliminatedFlavor }}</p>
          <div v-if="eliminationReason" class="font-arcade text-[10px] text-red-300 mb-6">
            REASON: {{ eliminationReasonLabel }}
          </div>
          <NuxtLink to="/" class="btn-3d btn-primary">
            <span class="text-xl">🏠</span>
            Back to Lobby
          </NuxtLink>
        </div>
      </div>
    </Transition>

    <!-- Victory overlay -->
    <Transition name="fade">
      <div v-if="isWinner" class="fixed inset-0 victory-bg flex items-center justify-center z-50 overflow-hidden">
        <div
          v-for="i in 40"
          :key="`confetti-${i}`"
          class="confetti"
          :style="confettiStyle(i)"
        >{{ confettiEmoji(i) }}</div>

        <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div class="burst burst-1"></div>
          <div class="burst burst-2"></div>
          <div class="burst burst-3"></div>
        </div>

        <div class="panel-3d p-10 text-center max-w-xl w-full mx-4 relative" style="border-color: rgba(250, 204, 21, 0.9); box-shadow: 0 0 60px rgba(250, 204, 21, 0.5);">
          <div class="text-9xl mb-4 animate-trophy-pop inline-block">🏆</div>
          <h2 class="title-3d text-6xl md:text-7xl mb-2 animate-rainbow">VICTORY!</h2>
          <p class="font-display text-lg text-amber-100 mb-2">{{ victoryFlavor }}</p>
          <div class="font-arcade text-[10px] text-amber-300 mb-6 animate-pulse">🎉 LAST PLAYER ALIVE 🎉</div>
          <NuxtLink to="/" class="btn-3d btn-primary">
            <span class="text-xl">🏠</span>
            Back to Lobby
          </NuxtLink>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import Scene from '~/components/Scene.vue'
import TaupeArena from '~/components/games/TaupeArena.vue'
import DotRushArena from '~/components/games/DotRushArena.vue'
import AmongUsArena from '~/components/games/AmongUsArena.vue'
import { useAuthStore } from '~/stores/auth'

const authStore = useAuthStore()
const layout = ref('QWERTY')
const gameType = ref('taupe')
const isWinner = ref(false)
const aliveCount = ref(1)
const isEliminated = ref(false)
const eliminationReason = ref(null)
const REASON_LABELS = {
  mistakes: 'TOO MANY MISTAKES',
  speed: 'TOO SLOW',
  disconnect: 'DISCONNECTED',
}
const eliminationReasonLabel = computed(() => {
  const r = eliminationReason.value
  if (!r) return ''
  return REASON_LABELS[r] || r.toUpperCase()
})
const route = useRoute()
const selectedSessionId = computed(() => route.query.sessionId || null)
const sessionStatus = ref('waiting')
const queueCount = ref(0)
const countdownValue = ref(null)
const gameStarted = computed(() => sessionStatus.value === 'running')
let countdownTimer = null
const chatMessages = ref([])
const chatInput = ref('')
const chatListEl = ref(null)
const socket = ref(null)

const arenaComponent = computed(() => {
  if (gameType.value === 'dot_rush') return DotRushArena
  if (gameType.value === 'among_us') return AmongUsArena
  return TaupeArena
})

const eliminatedFlavor = computed(() => {
  if (gameType.value === 'dot_rush') return 'You missed too many dots.'
  if (gameType.value === 'among_us') return 'You were eliminated from the game.'
  return 'The taupes got you.'
})
const victoryFlavor = computed(() => {
  if (gameType.value === 'dot_rush') return 'Sharpest clicker — that\'s you!'
  if (gameType.value === 'among_us') return 'Your team emerged victorious!'
  return 'Last taupe standing — that\'s you!'
})

function sendChat() {
  const text = chatInput.value.trim()
  if (!text || socket.value?.readyState !== 1) return
  socket.value.send(JSON.stringify({
    type: 'chat_message',
    data: { session_id: selectedSessionId.value, text }
  }))
  chatInput.value = ''
}

async function scrollChatToBottom() {
  await nextTick()
  if (chatListEl.value) chatListEl.value.scrollTop = chatListEl.value.scrollHeight
}

async function fetchSessionInfo() {
  if (!selectedSessionId.value) return
  try {
    const data = await $fetch(`/api/sessions/${selectedSessionId.value}`, { credentials: 'include' })
    const l = data?.config_json?.keyboard_layout
    if (l === 'QWERTY' || l === 'AZERTY' || l === 'NUMPAD') layout.value = l
    if (data?.game_type) gameType.value = data.game_type
    else if (data?.config_json?.game_type) gameType.value = data.config_json.game_type
    if (data?.status) sessionStatus.value = data.status
    if (typeof data?.queue_count === 'number') queueCount.value = data.queue_count
  } catch (e) { /* fall back */ }
}

onMounted(async () => {
  await fetchSessionInfo()
  if (!authStore.user) {
    try {
      const me = await $fetch('/api/me', { credentials: 'include' })
      if (me) authStore.setUser(me)
    } catch (e) { /* leave unauthenticated */ }
  }
  try {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const sid = selectedSessionId.value
    const wsUrl = `${proto}//${window.location.host}/ws${sid ? `?sessionId=${encodeURIComponent(sid)}` : ''}`
    console.log('Connecting to WebSocket:', wsUrl)
    const sock = new WebSocket(wsUrl)
    sock.onopen = () => console.log('✓ WebSocket connected')
    sock.onclose = () => console.log('✗ WebSocket closed')
    sock.onerror = (e) => console.error('✗ WebSocket error:', e)
    sock.addEventListener('message', handleSharedMessage)
    socket.value = sock
  } catch (e) { console.error('Error setting up WebSocket:', e) }
})

function handleSharedMessage(event) {
  let message
  try { message = JSON.parse(event.data) } catch { return }
  if (message.type === 'player_eliminated') {
    eliminationReason.value = message.data?.reason || null
    isEliminated.value = true
  }
  else if (message.type === 'alive_count') {
    aliveCount.value = message.data.count
  }
  else if (message.type === 'queue_joined' || message.type === 'queue_update') {
    if (!message.data?.session_id || message.data.session_id === selectedSessionId.value) {
      if (typeof message.data?.count === 'number') queueCount.value = message.data.count
    }
  }
  else if (message.type === 'countdown') {
    if (!message.data?.session_id || message.data.session_id === selectedSessionId.value) {
      countdownValue.value = message.data.seconds
      sessionStatus.value = 'running'
      if (countdownTimer) clearTimeout(countdownTimer)
      if (message.data.seconds === 0) {
        countdownTimer = setTimeout(() => { countdownValue.value = null }, 700)
      }
    }
  }
  else if (message.type === 'game_over') {
    if (!message.data?.session_id || message.data.session_id === selectedSessionId.value) {
      sessionStatus.value = 'ended'
      const me = authStore.user?.id
      if (me && message.data?.winner_id && message.data.winner_id === me) {
        isWinner.value = true
      }
    }
  }
  else if (message.type === 'chat') {
    if (selectedSessionId.value && message.data.session_id && message.data.session_id !== selectedSessionId.value) return
    chatMessages.value.push(message.data)
    if (chatMessages.value.length > 100) chatMessages.value.shift()
    scrollChatToBottom()
  }
}

onUnmounted(() => {
  if (socket.value) {
    socket.value.removeEventListener?.('message', handleSharedMessage)
    socket.value.close()
  }
  if (countdownTimer) clearTimeout(countdownTimer)
})

const CONFETTI_EMOJI = ['🎉', '🎊', '✨', '⭐', '🎆', '🎇', '🌟', '💫', '🏆', '🐹']
function confettiEmoji(i) { return CONFETTI_EMOJI[i % CONFETTI_EMOJI.length] }
function confettiStyle(i) {
  const left = (i * 137) % 100
  const delay = (i * 113) % 3000
  const duration = 2500 + (i * 97) % 2500
  const size = 18 + (i * 53) % 22
  const drift = ((i * 31) % 200) - 100
  return {
    left: `${left}%`,
    fontSize: `${size}px`,
    animationDelay: `${delay}ms`,
    animationDuration: `${duration}ms`,
    '--drift': `${drift}px`,
  }
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 300ms; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.animate-countdown-pop {
  animation: countdown-pop 900ms cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
@keyframes countdown-pop {
  0%   { transform: scale(0.2); opacity: 0; }
  35%  { transform: scale(1.25); opacity: 1; }
  60%  { transform: scale(1); }
  100% { transform: scale(1.1); opacity: 0.85; }
}

.victory-bg {
  background:
    radial-gradient(ellipse at center, rgba(250, 204, 21, 0.35) 0%, rgba(0, 0, 0, 0.85) 60%),
    rgba(0, 0, 0, 0.85);
  animation: victory-pulse 1.6s ease-in-out infinite;
}
@keyframes victory-pulse {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.25); }
}

.confetti {
  position: absolute;
  top: -10vh;
  pointer-events: none;
  user-select: none;
  animation-name: confetti-fall;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.4));
}
@keyframes confetti-fall {
  0%   { transform: translate(0, 0) rotate(0deg); opacity: 0; }
  10%  { opacity: 1; }
  100% { transform: translate(var(--drift), 110vh) rotate(720deg); opacity: 1; }
}

.animate-trophy-pop {
  animation: trophy-pop 1.2s cubic-bezier(0.34, 1.56, 0.64, 1) both, trophy-bob 2s ease-in-out 1.2s infinite;
  filter: drop-shadow(0 8px 16px rgba(250, 204, 21, 0.7));
}
@keyframes trophy-pop {
  0%   { transform: scale(0) rotate(-180deg); opacity: 0; }
  60%  { transform: scale(1.3) rotate(20deg); opacity: 1; }
  80%  { transform: scale(0.9) rotate(-10deg); }
  100% { transform: scale(1) rotate(0deg); }
}
@keyframes trophy-bob {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50%      { transform: translateY(-12px) rotate(4deg); }
}

.animate-rainbow {
  background: linear-gradient(90deg, #fde047, #fb923c, #f472b6, #a78bfa, #60a5fa, #34d399, #fde047);
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  animation: rainbow-slide 3s linear infinite;
  text-shadow: 0 4px 16px rgba(250, 204, 21, 0.4);
}
@keyframes rainbow-slide {
  0%   { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}

.burst {
  position: absolute;
  border-radius: 50%;
  border: 3px solid rgba(250, 204, 21, 0.8);
  width: 200px;
  height: 200px;
  animation: burst-expand 1.4s ease-out infinite;
  opacity: 0;
}
.burst-1 { animation-delay: 0s; }
.burst-2 { animation-delay: 0.45s; border-color: rgba(248, 113, 113, 0.7); }
.burst-3 { animation-delay: 0.9s; border-color: rgba(167, 139, 250, 0.7); }
@keyframes burst-expand {
  0%   { transform: scale(0.1); opacity: 1; border-width: 8px; }
  100% { transform: scale(5); opacity: 0; border-width: 1px; }
}
</style>
