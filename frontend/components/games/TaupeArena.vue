<template>
  <div class="contents">
    <!-- HUD -->
    <div class="relative z-20 flex justify-between items-center p-4 flex-wrap gap-3" style="max-width: calc(100vw - 244px); margin-right: auto;">
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

    <!-- Game Stage -->
    <div class="relative z-10 flex flex-col items-center gap-6 p-4" style="max-width: calc(100vw - 244px); margin-right: auto;">
      <div class="h-10 flex items-center">
        <div v-if="feedback" :class="['font-arcade text-xl animate-mole-pop drop-shadow-[0_3px_0_rgba(0,0,0,0.5)]', feedback.color]">
          {{ feedback.text }}
        </div>
        <div v-else-if="!gameStarted" class="font-arcade text-xs text-amber-300 animate-pulse text-center">
          ⏳ WAITING FOR ADMIN TO START · {{ queueCount }} 👥 IN QUEUE
        </div>
        <div v-else-if="!activeKey" class="text-purple-200/60 font-arcade text-xs animate-pulse">
          WAITING FOR TAUPE...
        </div>
      </div>

      <div class="relative">
        <Keyboard
          ref="keyboardRef"
          :active-key="activeKey"
          :wrong-key="wrongKey"
          :layout="layout"
          @key-press="handleKeyPress"
        />
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
          <div
            class="absolute left-1/2 bottom-1 -translate-x-1/2 w-10 h-4 rounded-full animate-dirt-puff"
            style="background: radial-gradient(ellipse, #6b3f20 0%, #a06a3e 50%, transparent 70%); filter: blur(1px);"
          ></div>
          <div class="absolute left-1/2 bottom-0 -translate-x-1/2 animate-mole-dig origin-bottom">
            <div class="text-4xl md:text-5xl drop-shadow-[0_3px_6px_rgba(0,0,0,0.8)]">🐹</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import Keyboard from '~/components/Keyboard.vue'

const props = defineProps({
  socket: { type: Object, default: null },
  sessionId: { type: String, default: null },
  gameStarted: { type: Boolean, default: false },
  queueCount: { type: Number, default: 0 },
  aliveCount: { type: Number, default: 1 },
  layout: { type: String, default: 'QWERTY' },
})

const emit = defineEmits(['session-running'])

const score = ref(0)
const currentRound = ref(0)
const combo = ref(0)
const activeKey = ref(null)
const activeRoundId = ref(null)
const wrongKey = ref(null)
const feedback = ref(null)
const keyboardRef = ref(null)
const molePosition = ref(null)
let feedbackTimer = null

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

function handleTaupeSpawn(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  const incomingKey = String(data?.key || '').toUpperCase()
  if (!incomingKey) return
  emit('session-running')
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
  if (props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'taupe_attempt',
      data: { round_id: roundId, key, client_ts: Date.now() }
    }))
  }
}

function onSocketMessage(event) {
  let message
  try { message = JSON.parse(event.data) } catch { return }
  if (message.type === 'taupe_spawn') handleTaupeSpawn(message.data)
}

watch(() => props.socket, (s, prev) => {
  if (prev) prev.removeEventListener?.('message', onSocketMessage)
  if (s) s.addEventListener('message', onSocketMessage)
}, { immediate: true })

onUnmounted(() => {
  if (props.socket) props.socket.removeEventListener?.('message', onSocketMessage)
  if (feedbackTimer) clearTimeout(feedbackTimer)
})

defineExpose({ score })
</script>
