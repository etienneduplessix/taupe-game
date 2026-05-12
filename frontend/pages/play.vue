<template>
  <div class="relative min-h-screen scanlines">
    <Scene />

    <!-- HUD -->
    <div v-if="gameStarted" class="relative z-20 flex justify-between items-center p-4 flex-wrap gap-3" style="max-width: calc(100vw - 244px); margin-right: auto;">
      <div class="flex gap-3 flex-wrap">
        <div class="chip">
          <span class="text-xl">💰</span>
          <div>
            <div class="font-arcade text-[9px] text-amber-300">SCORE</div>
            <div class="font-arcade text-xl text-yellow-300">{{ score.toString().padStart(5, '0') }}</div>
          </div>
        </div>
        <div class="chip">
          <span class="text-xl">🎯</span>
          <div>
            <div class="font-arcade text-[9px] text-amber-300">ROUND</div>
            <div class="font-arcade text-xl text-white">{{ currentRound.toString().padStart(3, '0') }}</div>
          </div>
        </div>
        <div class="chip">
          <span class="text-xl">🔥</span>
          <div>
            <div class="font-arcade text-[9px] text-amber-300">COMBO</div>
            <div class="font-arcade text-xl" :class="combo > 0 ? 'text-green-400' : 'text-gray-500'">×{{ combo }}</div>
          </div>
        </div>
        <div class="chip">
          <span class="text-xl">❤️</span>
          <div>
            <div class="font-arcade text-[9px] text-amber-300">ALIVE</div>
            <div class="font-arcade text-xl text-red-300">{{ aliveCount }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Waiting Room (queue) -->
    <div
      v-if="!gameStarted"
      class="relative z-10 flex flex-col items-center justify-center gap-5 p-8"
      style="max-width: calc(100vw - 244px); margin-right: auto; min-height: 80vh;"
    >
      <div class="panel-3d p-10 text-center max-w-lg w-full">
        <div class="text-6xl mb-4 animate-mole-bob">🐹</div>
        <h2 class="title-3d text-3xl md:text-4xl mb-3">WAITING ROOM</h2>
        <p class="font-display text-amber-100 mb-6">Hang tight — the admin will start the game soon.</p>
        <div class="chip !px-6 !py-3 mx-auto">
          <span class="text-2xl">👥</span>
          <div>
            <div class="font-arcade text-[9px] text-amber-300">PLAYERS QUEUED</div>
            <div class="font-arcade text-3xl text-yellow-300">{{ queueCount.toString().padStart(2, '0') }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Game Stage -->
    <div v-else class="relative z-10 flex flex-col items-center gap-6 p-4" style="max-width: calc(100vw - 244px); margin-right: auto;">
      <!-- Feedback -->
      <div class="h-10 flex items-center">
        <div v-if="feedback" :class="['font-arcade text-xl animate-mole-pop drop-shadow-[0_3px_0_rgba(0,0,0,0.5)]', feedback.color]">
          {{ feedback.text }}
        </div>
        <div v-else-if="!activeKey" class="text-purple-200/60 font-arcade text-xs animate-pulse">
          WAITING FOR TAUPE...
        </div>
      </div>

      <!-- Keyboard Container with Mole -->
      <div class="relative">
        <Keyboard
          ref="keyboardRef"
          :active-key="activeKey"
          :wrong-key="wrongKey"
          :layout="layout"
          @key-press="handleKeyPress"
        />
        <!-- Mole digs up out of the active key's hole -->
        <div
          v-if="activeKey && molePosition"
          :key="activeKey"
          class="absolute pointer-events-none overflow-visible"
          :style="{
            left: molePosition.x + 'px',
            top: molePosition.y + 'px',
            width: molePosition.width + 'px',
            height: molePosition.height + 'px',
          }"
        >
          <!-- Dirt puff -->
          <div
            class="absolute left-1/2 bottom-1 -translate-x-1/2 w-10 h-4 rounded-full animate-dirt-puff"
            style="background: radial-gradient(ellipse, #6b3f20 0%, #a06a3e 50%, transparent 70%); filter: blur(1px);"
          ></div>
          <!-- Mole emerging -->
          <div class="absolute left-1/2 bottom-0 -translate-x-1/2 animate-mole-dig origin-bottom">
            <div class="text-4xl md:text-5xl drop-shadow-[0_3px_6px_rgba(0,0,0,0.8)]">🐹</div>
          </div>
        </div>
      </div>
    </div>

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

    <!-- Eliminated overlay -->
    <Transition name="fade">
      <div v-if="isEliminated" class="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 scanlines">
        <div class="panel-3d p-10 text-center max-w-lg w-full mx-4" style="border-color: rgba(239,68,68,0.6);">
          <div class="text-8xl mb-4 animate-float">☠️</div>
          <h2 class="title-3d text-5xl md:text-6xl mb-4" style="color: #fca5a5;">ELIMINATED</h2>
          <p class="text-purple-200 mb-2 font-display">The taupes got you.</p>
          <div v-if="eliminationReason" class="font-arcade text-[10px] text-red-300 mb-6">
            REASON: {{ eliminationReasonLabel }}
          </div>
          <div class="chip !px-6 !py-3 mb-6 mx-auto">
            <span class="text-2xl">💰</span>
            <div>
              <div class="font-arcade text-[9px] text-amber-300">FINAL SCORE</div>
              <div class="font-arcade text-3xl text-yellow-300">{{ score.toString().padStart(5, '0') }}</div>
            </div>
          </div>
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
import Keyboard from '~/components/Keyboard.vue'
import Scene from '~/components/Scene.vue'

const layout = ref('QWERTY')
const score = ref(0)
const currentRound = ref(0)
const combo = ref(0)
const aliveCount = ref(1)
const activeKey = ref(null)
const activeRoundId = ref(null)
const wrongKey = ref(null)
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
const feedback = ref(null)
const keyboardRef = ref(null)
const molePosition = ref(null)
const route = useRoute()
const selectedSessionId = computed(() => route.query.sessionId || null)
const sessionStatus = ref('waiting')
const queueCount = ref(0)
const gameStarted = computed(() => sessionStatus.value === 'running')
const chatMessages = ref([])
const chatInput = ref('')
const chatListEl = ref(null)
let socket = null
let feedbackTimer = null

function sendChat() {
  const text = chatInput.value.trim()
  if (!text || socket?.readyState !== 1) return
  socket.send(JSON.stringify({
    type: 'chat_message',
    data: { session_id: selectedSessionId.value, text }
  }))
  chatInput.value = ''
}

async function scrollChatToBottom() {
  await nextTick()
  if (chatListEl.value) chatListEl.value.scrollTop = chatListEl.value.scrollHeight
}

function showFeedback(text, color) {
  feedback.value = { text, color }
  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => { feedback.value = null }, 600)
}

function updateMolePosition() {
  if (!activeKey.value || !keyboardRef.value) {
    molePosition.value = null
    return
  }
  const position = keyboardRef.value.getKeyPosition(activeKey.value)
  if (position) {
    molePosition.value = {
      x: position.x - position.width / 2,
      y: position.y,
      width: position.width,
      height: position.height,
    }
  }
}

watch(activeKey, updateMolePosition)
onUpdated(updateMolePosition)

async function fetchSessionInfo() {
  if (!selectedSessionId.value) return
  try {
    const data = await $fetch(`/api/admin/sessions/${selectedSessionId.value}`, { credentials: 'include' })
    const l = data?.config_json?.keyboard_layout
    if (l === 'QWERTY' || l === 'AZERTY' || l === 'NUMPAD') layout.value = l
    if (data?.status) sessionStatus.value = data.status
    if (typeof data?.queue_count === 'number') queueCount.value = data.queue_count
  } catch (e) { /* fall back to QWERTY */ }
}

onMounted(() => {
  fetchSessionInfo()
  try {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const sid = selectedSessionId.value
    const wsUrl = `${proto}//${window.location.host}/ws${sid ? `?sessionId=${encodeURIComponent(sid)}` : ''}`
    console.log('Connecting to WebSocket:', wsUrl)
    socket = new WebSocket(wsUrl)
    socket.onopen = () => console.log('✓ WebSocket connected')
    socket.onclose = () => console.log('✗ WebSocket closed')
    socket.onerror = (e) => console.error('✗ WebSocket error:', e)
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data)
      console.log('📨 Message received:', message.type)
      if (message.type === 'taupe_spawn') {
        if (selectedSessionId.value && message.data.session_id && message.data.session_id !== selectedSessionId.value) return
        sessionStatus.value = 'running'
        handleTaupeSpawn(message.data)
      }
      else if (message.type === 'player_eliminated') {
        eliminationReason.value = message.data?.reason || null
        isEliminated.value = true
      }
      else if (message.type === 'alive_count') aliveCount.value = message.data.count
      else if (message.type === 'queue_joined' || message.type === 'queue_update') {
        if (!message.data?.session_id || message.data.session_id === selectedSessionId.value) {
          if (typeof message.data?.count === 'number') queueCount.value = message.data.count
        }
      }
      else if (message.type === 'game_over') {
        if (!message.data?.session_id || message.data.session_id === selectedSessionId.value) {
          sessionStatus.value = 'ended'
        }
      }
      else if (message.type === 'chat') {
        if (selectedSessionId.value && message.data.session_id && message.data.session_id !== selectedSessionId.value) return
        chatMessages.value.push(message.data)
        if (chatMessages.value.length > 100) chatMessages.value.shift()
        scrollChatToBottom()
      }
    }
  } catch (e) { console.error('Error setting up WebSocket:', e) }
})

function handleTaupeSpawn(data) {
  const incomingKey = String(data?.key || '').toUpperCase()
  if (!incomingKey) return
  const roundId = data?.round_id || null
  activeKey.value = incomingKey
  activeRoundId.value = roundId
  currentRound.value++
  setTimeout(() => {
    if (activeKey.value === incomingKey && activeRoundId.value === roundId) {
      activeKey.value = null
      activeRoundId.value = null
      combo.value = 0
      showFeedback('TOO SLOW!', 'text-orange-400')
    }
  }, data.timeout_ms)
}

function handleKeyPress(key) {
  if (!activeKey.value) return
  const roundId = activeRoundId.value
  if (key === activeKey.value) {
    activeKey.value = null
    activeRoundId.value = null
    combo.value++
    const points = 100 * (combo.value >= 10 ? 3 : combo.value >= 5 ? 2 : 1)
    score.value += points
    showFeedback(`+${points} HIT!`, 'text-green-400')
  } else {
    combo.value = 0
    wrongKey.value = key
    setTimeout(() => { wrongKey.value = null }, 300)
    showFeedback('MISS!', 'text-red-400')
  }
  if (socket?.readyState === 1) {
    socket.send(JSON.stringify({
      type: 'taupe_attempt',
      data: { round_id: roundId, key, client_ts: Date.now() }
    }))
  }
}

onUnmounted(() => {
  if (socket) socket.close()
  if (feedbackTimer) clearTimeout(feedbackTimer)
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 300ms; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
