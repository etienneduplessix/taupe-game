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
          <span class="text-xl">💔</span>
          <div>
            <div class="font-arcade text-[9px] text-amber-300">MISSES</div>
            <div class="font-arcade text-xl" :class="misses >= maxMisses - 1 ? 'text-red-400 animate-pulse' : 'text-orange-300'">
              {{ misses }} / {{ maxMisses }}
            </div>
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
    <div class="relative z-10 flex flex-col items-center gap-4 p-4" style="max-width: calc(100vw - 244px); margin-right: auto;">
      <div class="h-10 flex items-center">
        <div v-if="feedback" :class="['font-arcade text-xl animate-mole-pop drop-shadow-[0_3px_0_rgba(0,0,0,0.5)]', feedback.color]">
          {{ feedback.text }}
        </div>
        <div v-else-if="!gameStarted" class="font-arcade text-xs text-amber-300 animate-pulse text-center">
          ⏳ WAITING FOR ADMIN TO START · {{ queueCount }} 👥 IN QUEUE
        </div>
        <div v-else-if="!activeDot" class="text-purple-200/60 font-arcade text-xs animate-pulse">
          WATCH FOR THE DOT...
        </div>
        <div v-else class="font-arcade text-xs text-amber-300">CLICK THE DOT!</div>
      </div>

      <div
        ref="canvasEl"
        class="dot-canvas relative overflow-hidden rounded-2xl cursor-crosshair"
        @click="handleCanvasClick"
      >
        <Transition name="dot-fade">
          <div
            v-if="activeDot"
            :key="activeDot.round_id"
            class="dot absolute rounded-full pointer-events-none"
            :style="dotStyle"
          ></div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  socket: { type: Object, default: null },
  sessionId: { type: String, default: null },
  gameStarted: { type: Boolean, default: false },
  queueCount: { type: Number, default: 0 },
  aliveCount: { type: Number, default: 1 },
})

const emit = defineEmits(['session-running'])

const score = ref(0)
const currentRound = ref(0)
const misses = ref(0)
const maxMisses = ref(3)
const activeDot = ref(null)
const feedback = ref(null)
const canvasEl = ref(null)
let feedbackTimer = null
let dotExpireTimer = null

const dotStyle = computed(() => {
  if (!activeDot.value) return {}
  const r = activeDot.value.radius_pct
  return {
    left: `${activeDot.value.x - r}%`,
    top: `${activeDot.value.y - r}%`,
    width: `${r * 2}%`,
    height: `${r * 2}%`,
    background: 'radial-gradient(circle, #fde047 0%, #f59e0b 60%, #b45309 100%)',
    boxShadow: '0 0 24px rgba(250, 204, 21, 0.7), 0 4px 12px rgba(0,0,0,0.5)',
    border: '3px solid #fff7ed',
  }
})

function showFeedback(text, color) {
  feedback.value = { text, color }
  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => { feedback.value = null }, 600)
}

function handleCanvasClick(e) {
  if (!activeDot.value || !canvasEl.value) return
  const rect = canvasEl.value.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  const dot = activeDot.value
  const dx = x - dot.x
  const dy = y - dot.y
  const inside = Math.hypot(dx, dy) <= dot.radius_pct
  if (inside) {
    // Optimistic: clear locally; server confirms via dot_resolved
    activeDot.value = null
    if (dotExpireTimer) { clearTimeout(dotExpireTimer); dotExpireTimer = null }
    showFeedback('HIT!', 'text-green-400')
  }
  if (props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'dot_click',
      data: { round_id: dot.round_id, x, y, client_ts: Date.now() }
    }))
  }
}

function handleDotSpawn(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  emit('session-running')
  currentRound.value = data.round_number || (currentRound.value + 1)
  activeDot.value = {
    round_id: data.round_id,
    x: data.x,
    y: data.y,
    radius_pct: data.radius_pct,
    lifetime_ms: data.lifetime_ms,
  }
  if (dotExpireTimer) clearTimeout(dotExpireTimer)
  dotExpireTimer = setTimeout(() => {
    if (activeDot.value && activeDot.value.round_id === data.round_id) {
      activeDot.value = null
    }
  }, data.lifetime_ms + 100)
}

function handleDotResolved(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  if (activeDot.value && activeDot.value.round_id === data.round_id) {
    activeDot.value = null
  }
  if (data.expired) {
    showFeedback('TOO SLOW!', 'text-orange-400')
  } else if (data.winner_id) {
    // Score is server-authoritative; bump local counter for visual feedback only when it's ours.
    // Without auth user_id wired here, just give a soft "scored" indicator on the winner side.
    // Parent owns auth state; emit so parent can resolve identity if needed.
    emit('dot-claimed', data)
  }
}

function handleDotMiss(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  misses.value = data.misses
  if (typeof data.max_misses === 'number') maxMisses.value = data.max_misses
  showFeedback('MISS!', 'text-red-400')
}

function onSocketMessage(event) {
  let message
  try { message = JSON.parse(event.data) } catch { return }
  if (message.type === 'dot_spawn') handleDotSpawn(message.data)
  else if (message.type === 'dot_resolved') handleDotResolved(message.data)
  else if (message.type === 'dot_miss') handleDotMiss(message.data)
}

watch(() => props.socket, (s, prev) => {
  if (prev) prev.removeEventListener?.('message', onSocketMessage)
  if (s) s.addEventListener('message', onSocketMessage)
}, { immediate: true })

defineExpose({
  registerHit(latencyMs) {
    const points = Math.max(1, Math.round(100 - (latencyMs || 0) / 10))
    score.value += points
    showFeedback(`+${points} HIT!`, 'text-green-400')
  },
})

onUnmounted(() => {
  if (props.socket) props.socket.removeEventListener?.('message', onSocketMessage)
  if (feedbackTimer) clearTimeout(feedbackTimer)
  if (dotExpireTimer) clearTimeout(dotExpireTimer)
})
</script>

<style scoped>
.dot-canvas {
  width: min(70vw, calc(100vw - 280px));
  aspect-ratio: 16 / 9;
  background:
    radial-gradient(ellipse at top, rgba(167, 139, 250, 0.18), transparent 60%),
    radial-gradient(ellipse at bottom, rgba(248, 113, 113, 0.12), transparent 60%),
    #1a0f08;
  border: 3px solid rgba(251, 191, 36, 0.45);
  box-shadow:
    inset 0 4px 12px rgba(0, 0, 0, 0.6),
    0 8px 24px rgba(0, 0, 0, 0.5);
}

.dot {
  animation: dot-pop 180ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes dot-pop {
  0%   { transform: scale(0.2); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

.dot-fade-enter-active, .dot-fade-leave-active { transition: opacity 120ms, transform 120ms; }
.dot-fade-enter-from, .dot-fade-leave-to { opacity: 0; transform: scale(0.6); }
</style>
