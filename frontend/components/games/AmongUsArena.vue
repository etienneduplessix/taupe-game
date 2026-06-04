<template>
  <div class="contents">
    <!-- HUD -->
    <div class="relative z-20 flex justify-between items-center p-4 flex-wrap gap-3" style="max-width: calc(100vw - 244px); margin-right: auto;">
      <div class="flex gap-3 flex-wrap">
        <div class="chip">
          <span class="text-xl">🕵️</span>
          <div>
            <div class="font-arcade text-[9px] text-amber-300">ROLE</div>
            <div class="font-arcade text-xl" :class="roleColorClass">{{ myRole }}</div>
          </div>
        </div>
        <div class="chip">
          <span class="text-xl">📋</span>
          <div>
            <div class="font-arcade text-[9px] text-amber-300">TASKS</div>
            <div class="font-arcade text-xl text-green-300">{{ tasksCompleted }} / {{ tasksTotal }}</div>
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
      <div v-if="myRole === 'impostor'" class="flex gap-2">
        <button @click="sendKill" :disabled="killCooldown > 0" class="btn-3d btn-danger !py-2 !px-3 !text-xs">
          🔪 KILL {{ killCooldown > 0 ? `(${Math.ceil(killCooldown)}s)` : '' }}
        </button>
        <button @click="sendSabotage" class="btn-3d btn-secondary !py-2 !px-3 !text-xs">
          ⚡ SABOTAGE
        </button>
      </div>
    </div>

    <!-- Task progress bar -->
    <div v-if="tasksTotal > 0" class="relative z-20 px-4 pb-2" style="max-width: calc(100vw - 244px); margin-right: auto;">
      <div class="h-2 bg-black/40 rounded-full overflow-hidden border border-amber-400/30">
        <div class="h-full bg-gradient-to-r from-green-400 to-emerald-500 transition-all duration-300" :style="{ width: `${(tasksCompleted / tasksTotal) * 100}%` }"></div>
      </div>
    </div>

    <!-- Game Canvas -->
    <div class="relative z-10 flex flex-col items-center gap-4 p-4" style="max-width: calc(100vw - 244px); margin-right: auto;">
      <div v-if="!gameStarted" class="font-arcade text-xs text-amber-300 animate-pulse text-center py-10">
        ⏳ WAITING FOR ADMIN TO START · {{ queueCount }} 👥 IN QUEUE
      </div>
      <div v-else class="flex items-start justify-center gap-4 max-w-full">
        <div class="relative shrink min-w-0">
          <canvas
            ref="canvasEl"
            :width="canvasWidth"
            :height="canvasHeight"
            class="rounded-2xl cursor-crosshair border-4 border-amber-400/40 max-w-full h-auto"
            tabindex="0"
            @keyup.stop.prevent="handleKeyUp"
            @keydown.stop.prevent="handleKeyDown"
            @blur="focused = false"
            @focus="focused = true"
            @click="handleCanvasClick"
          ></canvas>
          <div v-if="!focused" class="absolute inset-0 flex items-center justify-center bg-black/60 rounded-2xl pointer-events-none">
            <div class="font-arcade text-sm text-amber-300 text-center px-4">CLICK MAP TO FOCUS<br><span class="text-xs opacity-70">Use WASD or Arrow Keys to move</span></div>
          </div>
          <button
            v-if="nearbyTask && !activeTask"
            type="button"
            class="absolute left-1/2 bottom-4 -translate-x-1/2 btn-3d btn-primary !py-2 !px-4 !text-[10px] z-20"
            @click.stop="tryStartTask"
          >
            TASK: {{ nearbyTask.label }} · E
          </button>
        </div>
        <div class="shrink-0 rounded-xl border-2 border-amber-400/50 bg-[#0b1020]/85 p-2 shadow-[0_0_24px_rgba(0,0,0,0.45)]">
          <div class="font-arcade text-[8px] text-amber-300 mb-2 text-center">MAP</div>
          <canvas
            ref="miniMapEl"
            :width="miniMapWidth"
            :height="miniMapHeight"
            class="block rounded-lg border border-amber-400/30"
          ></canvas>
        </div>
      </div>
    </div>

    <!-- Task Overlay -->
    <Transition name="fade">
      <div v-if="activeTask" class="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
        <div class="panel-3d p-6 max-w-sm w-full">
          <h3 class="title-3d text-xl mb-4 text-center">{{ activeTask.label }}</h3>
          <div v-if="activeTask.type === 'button_press' || activeTask.type === 'swipe_card' || activeTask.type === 'upload_data'" class="text-center">
            <div class="h-4 bg-black/40 rounded-full overflow-hidden mb-4">
              <div class="h-full bg-gradient-to-r from-green-400 to-emerald-500 transition-all duration-100" :style="{ width: `${taskProgress}%` }"></div>
            </div>
            <p class="font-arcade text-[10px] text-amber-300 mb-2">HOLD E OR CLICK TO COMPLETE</p>
            <button @mousedown="startTaskHold" @mouseup="stopTaskHold" @mouseleave="stopTaskHold" @touchstart.prevent="startTaskHold" @touchend.prevent="stopTaskHold" class="btn-3d btn-primary !py-3 !px-6">
              {{ taskHolding ? '...' : 'HOLD' }}
            </button>
          </div>
          <div v-else-if="activeTask.type === 'wire_connect'" class="flex flex-col gap-2">
            <p class="font-arcade text-[10px] text-amber-300 text-center mb-2">CLICK IN ORDER: {{ activeTask.sequence.join(' → ') }}</p>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="wire in wireOptions"
                :key="wire"
                @click="clickWire(wire)"
                class="btn-3d !py-2 !text-sm"
                :class="wireColor(wire)"
              >
                {{ wire }}
              </button>
            </div>
            <div v-if="wireStep > 0" class="font-arcade text-[10px] text-amber-300 text-center mt-2">{{ wireStep }} / {{ activeTask.sequence.length }}</div>
          </div>
          <div v-else-if="activeTask.type === 'calibrate'" class="text-center">
            <p class="font-arcade text-[10px] text-amber-300 mb-3">CLICK 3 TIMES</p>
            <div class="font-arcade text-4xl text-green-400 mb-3">{{ calibrateDone }} / 3</div>
            <button @click="calibrateClick" class="btn-3d btn-primary !py-3 !px-6 text-2xl">🔧</button>
          </div>
          <div class="flex justify-center mt-4">
            <button @click="cancelTask" class="btn-3d btn-ghost !py-1 !px-3 text-xs">Cancel</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Meeting Overlay -->
    <Transition name="fade">
      <div v-if="meetingState" class="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
        <div class="panel-3d p-6 max-w-lg w-full">
          <h3 class="title-3d text-2xl mb-4 text-center">
            {{ meetingState.phase === 'discussion' ? '🚨 EMERGENCY MEETING' : '🗳️ VOTING' }}
          </h3>
          <div v-if="meetingState.phase === 'discussion'" class="text-center">
            <div class="font-arcade text-4xl text-red-400 mb-4 animate-pulse">{{ meetingTimer }}s</div>
            <p class="font-arcade text-[10px] text-amber-300">DISCUSS WITH CHAT — VOTING STARTS SOON</p>
          </div>
          <div v-else>
            <div class="font-arcade text-xl text-amber-300 text-center mb-4">{{ meetingTimer }}s</div>
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="p in meetingState.participants"
                :key="p.id"
                @click="vote(p.id)"
                class="btn-3d !py-2 !text-xs"
                :class="myVote === p.id ? 'btn-primary' : 'btn-ghost'"
              >
                <span class="w-3 h-3 rounded-full inline-block mr-1" :style="{ background: p.color }"></span>
                {{ p.display_name }}
              </button>
              <button @click="vote('skip')" class="btn-3d !py-2 !text-xs" :class="myVote === 'skip' ? 'btn-secondary' : 'btn-ghost'">
                ⏭️ SKIP
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Meeting Result -->
    <Transition name="fade">
      <div v-if="meetingResult" class="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
        <div class="panel-3d p-8 max-w-md w-full text-center">
          <div class="text-6xl mb-4">{{ meetingResult.ejected_id ? '💀' : '🤷' }}</div>
          <h3 class="title-3d text-2xl mb-2">
            {{ meetingResult.ejected_id ? `${meetingResult.ejected_name} WAS EJECTED` : 'NOBODY WAS EJECTED' }}
          </h3>
          <p v-if="meetingResult.ejected_id" class="font-arcade text-[10px] text-amber-300 mb-4">
            {{ meetingResult.ejected_was_impostor ? 'THEY WERE AN IMPOSTOR!' : 'THEY WERE NOT AN IMPOSTOR...' }}
          </p>
          <button @click="meetingResult = null" class="btn-3d btn-primary !py-2 !px-4">
            CONTINUE
          </button>
        </div>
      </div>
    </Transition>

    <!-- Game Over -->
    <Transition name="fade">
      <div v-if="gameOver" class="fixed inset-0 victory-bg flex items-center justify-center z-50 overflow-hidden">
        <div class="panel-3d p-10 text-center max-w-xl w-full mx-4 relative" :style="{ borderColor: gameOver.winner === 'crewmates' ? 'rgba(34,197,94,0.8)' : 'rgba(239,68,68,0.8)', boxShadow: `0 0 60px ${gameOver.winner === 'crewmates' ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}` }">
          <div class="text-8xl mb-4">{{ gameOver.winner === 'crewmates' ? '👨‍🚀' : '👹' }}</div>
          <h2 class="title-3d text-5xl md:text-6xl mb-4" :class="gameOver.winner === 'crewmates' ? 'text-green-300' : 'text-red-300'">
            {{ gameOver.winner === 'crewmates' ? 'CREWMATES WIN!' : 'IMPOSTORS WIN!' }}
          </h2>
          <p class="font-display text-lg text-amber-100 mb-6">
            {{ gameOver.winner === 'crewmates' ? 'All tasks completed or impostors eliminated!' : 'Crewmates were outnumbered!' }}
          </p>
          <div class="font-arcade text-[10px] text-amber-300 mb-6">
            IMPOSTORS: {{ gameOver.impostors.map(id => playerNames[id] || id).join(', ') }}
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
import { useAuthStore } from '~/stores/auth'

const props = defineProps({
  socket: { type: Object, default: null },
  sessionId: { type: String, default: null },
  gameStarted: { type: Boolean, default: false },
  queueCount: { type: Number, default: 0 },
  aliveCount: { type: Number, default: 1 },
})

const emit = defineEmits(['session-running'])

// Auth
const authStore = useAuthStore()
const myUserId = computed(() => authStore.user?.id || 'me')

// Map & Canvas
const canvasEl = ref(null)
const miniMapEl = ref(null)
const focused = ref(false)
let TILE_SIZE = 32
const canvasWidth = ref(760)
const canvasHeight = ref(540)
const miniMapWidth = ref(150)
const miniMapHeight = ref(246)
const worldWidth = ref(704)
const worldHeight = ref(1152)
let ctx = null
let miniCtx = null

// Map data
const mapData = ref(null)
const walls = ref(new Set())
const floorTiles = ref([])
const taskZones = ref([])
const spawns = ref([])
const bgImage = ref(null)
const bgReady = ref(false)
const bgCrop = ref(null)

// Game state
const myRole = ref('crewmate')
const myColor = ref('#3b82f6')
const tasksAssigned = ref([])
const tasksCompleted = ref(0)
const tasksTotal = ref(0)
const killCooldown = ref(0)
const gameOver = ref(null)
const meetingState = ref(null)
const meetingResult = ref(null)
const meetingTimer = ref(0)
const myVote = ref(null)

// Players
const players = ref({})
const deadBodies = ref([])
const lightsOut = ref(false)
const playerNames = ref({})

// Movement
const keys = ref({})
const myPos = ref({ x: 5.5, y: 5.5 })
let moveInterval = null
let lastMoveSent = 0
const MOVE_SEND_INTERVAL = 50

// Task
const activeTask = ref(null)
const taskProgress = ref(0)
const taskHolding = ref(false)
let taskHoldInterval = null
const wireStep = ref(0)
const wireOptions = ref(['A', 'B', 'C', 'D'])
const calibrateDone = ref(0)
const completedTaskIds = ref([])
const TASK_INTERACT_DISTANCE = 1.35

const nearbyTask = computed(() => {
  if (myRole.value !== 'crewmate' || !mapData.value || activeTask.value) return null
  let nearest = null
  let nearestDistance = Infinity
  for (const zone of taskZones.value) {
    if (!tasksAssigned.value.includes(zone.id)) continue
    if (completedTaskIds.value.includes(zone.id)) continue
    const distance = Math.hypot((zone.x + 0.5) - myPos.value.x, (zone.y + 0.5) - myPos.value.y)
    if (distance <= TASK_INTERACT_DISTANCE && distance < nearestDistance) {
      nearest = zone
      nearestDistance = distance
    }
  }
  return nearest
})

// Load map
async function loadMap() {
  try {
    const data = await $fetch('/maps/campus.json')
    mapData.value = data
    TILE_SIZE = data.tile_size || 32
    const crop = data.background_crop
    if (crop) {
      TILE_SIZE = crop.w / data.width
      worldWidth.value = crop.w
      worldHeight.value = crop.h
    } else {
      worldWidth.value = data.width * TILE_SIZE
      worldHeight.value = data.height * TILE_SIZE
    }
    canvasWidth.value = Math.min(worldWidth.value, 760)
    canvasHeight.value = Math.min(worldHeight.value, 540)
    parseMap(data)
    loadBackground(data)
  } catch (e) {
    console.error('Failed to load map', e)
  }
}

function loadBackground(data) {
  if (!data.background) return
  bgCrop.value = data.background_crop || null
  const img = new Image()
  img.onload = () => { bgReady.value = true }
  img.src = data.background
  bgImage.value = img
}

function parseMap(data) {
  walls.value.clear()
  floorTiles.value = []
  taskZones.value = []
  spawns.value = data.spawns || []

  data.tiles.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      const ch = row[x]
      if (ch === 'W') {
        walls.value.add(`${x},${y}`)
      } else if (ch >= '1' && ch <= '8') {
        floorTiles.value.push({ x, y })
        const tid = 'T' + ch
        const zone = data.task_zones[tid]
        if (zone) {
          taskZones.value.push({ x, y, id: tid, ...zone })
        }
      } else {
        floorTiles.value.push({ x, y })
      }
    }
  })
}

// Movement
function handleKeyDown(e) {
  if (isTypingTarget(e.target)) return
  const key = e.key.toLowerCase()
  if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(key)) {
    keys.value[key] = true
    focused.value = true
    e.preventDefault()
    updatePosition()
    if (!moveInterval) startMovementLoop()
  }
  if (key === 'e') {
    e.preventDefault()
    if (isTimedTask(activeTask.value)) {
      startTaskHold()
    } else {
      tryStartTask()
    }
  }
  if (key === 'r') {
    e.preventDefault()
    tryReport()
  }
  if (key === 'q' && myRole.value === 'impostor') {
    e.preventDefault()
    tryAutoKill()
  }
}

function handleKeyUp(e) {
  if (isTypingTarget(e.target)) return
  const key = e.key.toLowerCase()
  keys.value[key] = false
  if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(key)) {
    e.preventDefault()
  }
  if (key === 'e') {
    stopTaskHold()
  }
}

function resetMovementKeys() {
  keys.value = {}
}

function isTypingTarget(target) {
  const tag = target?.tagName?.toLowerCase()
  return tag === 'input' || tag === 'textarea' || target?.isContentEditable
}

function startMovementLoop() {
  if (moveInterval) return
  moveInterval = setInterval(() => {
    updatePosition()
  }, 16)
}

function updatePosition() {
  if (!mapData.value || !myRole.value) return

  const speed = 0.12
  let dx = 0, dy = 0
  if (keys.value['w'] || keys.value['arrowup']) dy -= speed
  if (keys.value['s'] || keys.value['arrowdown']) dy += speed
  if (keys.value['a'] || keys.value['arrowleft']) dx -= speed
  if (keys.value['d'] || keys.value['arrowright']) dx += speed

  if (dx === 0 && dy === 0) return

  const newX = Math.max(0.5, Math.min(mapData.value.width - 0.5, myPos.value.x + dx))
  const newY = Math.max(0.5, Math.min(mapData.value.height - 0.5, myPos.value.y + dy))

  // Wall collision check
  if (!isWall(newX, newY)) {
    myPos.value.x = newX
    myPos.value.y = newY
  }

  const now = Date.now()
  if (now - lastMoveSent > MOVE_SEND_INTERVAL) {
    lastMoveSent = now
    if (props.socket?.readyState === 1) {
      props.socket.send(JSON.stringify({
        type: 'among_us_move',
        data: { x: myPos.value.x, y: myPos.value.y }
      }))
    }
  }
}

function isWall(x, y) {
  const margin = 0.2
  const checks = [
    [x + margin, y + margin],
    [x - margin, y + margin],
    [x + margin, y - margin],
    [x - margin, y - margin]
  ]
  return checks.some(([cx, cy]) => walls.value.has(`${Math.floor(cx)},${Math.floor(cy)}`))
}

// Rendering
function render() {
  if (!ctx || !canvasEl.value) return
  if (!mapData.value) return

  const camera = getCamera()
  renderMiniMap(camera)

  ctx.clearRect(0, 0, canvasWidth.value, canvasHeight.value)
  ctx.save()
  ctx.translate(-camera.x, -camera.y)

  // Draw background (campus SVG cropped to building interior)
  ctx.fillStyle = '#0a0e17'
  ctx.fillRect(0, 0, worldWidth.value, worldHeight.value)
  if (bgReady.value && bgImage.value) {
    const c = bgCrop.value
    if (c) {
      ctx.drawImage(bgImage.value, c.x, c.y, c.w, c.h, 0, 0, worldWidth.value, worldHeight.value)
    } else {
      ctx.drawImage(bgImage.value, 0, 0, worldWidth.value, worldHeight.value)
    }
  } else {
    // Fallback: procedural floor until the SVG loads
    ctx.fillStyle = '#16213e'
    floorTiles.value.forEach(({ x, y }) => {
      ctx.fillRect(x * TILE_SIZE + 1, y * TILE_SIZE + 1, TILE_SIZE - 2, TILE_SIZE - 2)
    })
  }

  // Wall overlay — always drawn so the game grid is visible
  walls.value.forEach(key => {
    const [x, y] = key.split(',').map(Number)
    const wx = x * TILE_SIZE
    const wy = y * TILE_SIZE
    ctx.fillStyle = 'rgba(15, 15, 35, 0.55)'
    ctx.fillRect(wx, wy, TILE_SIZE, TILE_SIZE)
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.35)'
    ctx.lineWidth = 1
    ctx.strokeRect(wx + 1, wy + 1, TILE_SIZE - 2, TILE_SIZE - 2)
  })

  // Draw task zones (highlight)
  taskZones.value.forEach(zone => {
    const isAssigned = tasksAssigned.value.includes(zone.id)
    const isDone = completedTaskIds.value.includes(zone.id)
    const isNearby = nearbyTask.value?.id === zone.id
    ctx.fillStyle = isDone
      ? 'rgba(148, 163, 184, 0.12)'
      : isAssigned
        ? (isNearby ? 'rgba(250, 204, 21, 0.34)' : 'rgba(34, 197, 94, 0.22)')
        : 'rgba(34, 197, 94, 0.10)'
    ctx.fillRect(zone.x * TILE_SIZE, zone.y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
    ctx.strokeStyle = isDone
      ? 'rgba(148, 163, 184, 0.45)'
      : isNearby
        ? 'rgba(250, 204, 21, 0.95)'
        : 'rgba(34, 197, 94, 0.6)'
    ctx.lineWidth = isNearby ? 4 : 2
    ctx.strokeRect(zone.x * TILE_SIZE + 2, zone.y * TILE_SIZE + 2, TILE_SIZE - 4, TILE_SIZE - 4)

    if (isAssigned && !isDone) {
      ctx.font = '8px "Press Start 2P"'
      ctx.fillStyle = isNearby ? '#fde68a' : '#bbf7d0'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('TASK', (zone.x + 0.5) * TILE_SIZE, (zone.y - 0.15) * TILE_SIZE)
    }
  })

  // Draw dead bodies
  deadBodies.value.forEach(body => {
    ctx.fillStyle = body.color || '#888'
    ctx.globalAlpha = 0.7
    const bx = body.x * TILE_SIZE
    const by = body.y * TILE_SIZE
    ctx.fillRect(bx - 10, by - 10, 20, 20)
    ctx.fillStyle = '#fff'
    ctx.font = '12px "Press Start 2P"'
    ctx.textAlign = 'center'
    ctx.fillText('💀', bx, by - 15)
    ctx.globalAlpha = 1.0
  })

  // Draw players
  const allPlayers = Object.values(players.value)
  const myId = getMyId()
  const myVision = getMyVisionRadius()

  allPlayers.forEach(p => {
    const px = p.x * TILE_SIZE
    const py = p.y * TILE_SIZE
    const isMe = p.id === myId
    const isGhost = !p.alive
    const isImpostor = p.role === 'impostor'
    const dist = Math.hypot(p.x - myPos.value.x, p.y - myPos.value.y)
    const inVision = dist <= myVision || isMe

    if (!inVision && !isGhost) return

    ctx.globalAlpha = 1.0

    // Floor shadow
    ctx.fillStyle = 'rgba(0,0,0,0.35)'
    ctx.beginPath()
    ctx.ellipse(px, py + 4, 14, 6, 0, 0, Math.PI * 2)
    ctx.fill()

    // Body circle (colored)
    ctx.fillStyle = (isGhost ? '#666' : p.color || '#3b82f6')
    ctx.globalAlpha = isGhost ? 0.3 : 0.85
    ctx.beginPath()
    ctx.arc(px, py - 4, 14, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = isGhost ? '#444' : '#fff'
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.globalAlpha = isGhost ? 0.4 : 1.0

    // Emoji face
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    let emoji = '👩‍🚀'
    if (isGhost) {
      emoji = '👻'
    } else if (isImpostor && (isMe)) {
      emoji = '👹'
    }

    // Idle bobbing animation
    const bobY = Math.sin(Date.now() * 0.003 + (p.id || '').charCodeAt(0)) * 2
    ctx.font = '22px serif'
    ctx.fillText(emoji, px, py - 6 + bobY)

    // Name tag
    ctx.font = '9px "Press Start 2P"'
    ctx.fillStyle = '#fff'
    ctx.textBaseline = 'alphabetic'
    ctx.fillText(p.display_name || p.id, px, py - 22)

    // Role badge (only for self)
    if (isMe && !isGhost) {
      ctx.fillStyle = isImpostor ? '#ef4444' : '#22c55e'
      ctx.font = '7px "Press Start 2P"'
      ctx.fillText(isImpostor ? 'IMPOSTOR' : 'CREWMATE', px, py + 24)
    }

    // Kill cooldown indicator for impostor
    if (isImpostor && isMe && killCooldown.value > 0) {
      ctx.fillStyle = '#fbbf24'
      ctx.font = '8px "Press Start 2P"'
      ctx.fillText('🔪 ' + Math.ceil(killCooldown.value) + 's', px, py + 36)
    }

    ctx.globalAlpha = 1.0
  })

  // Vision radius overlay (darken outside)
  if (lightsOut.value && myRole.value !== 'impostor') {
    const visionPx = myVision * TILE_SIZE
    const mx = myPos.value.x * TILE_SIZE - camera.x
    const my = myPos.value.y * TILE_SIZE - camera.y

    ctx.restore()

    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)'
    ctx.fillRect(0, 0, canvasWidth.value, canvasHeight.value)

    ctx.globalCompositeOperation = 'destination-out'
    const gradient = ctx.createRadialGradient(mx, my, 0, mx, my, visionPx)
    gradient.addColorStop(0, 'rgba(0,0,0,1)')
    gradient.addColorStop(0.7, 'rgba(0,0,0,0.8)')
    gradient.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.arc(mx, my, visionPx, 0, Math.PI * 2)
    ctx.fill()
    ctx.globalCompositeOperation = 'source-over'
  } else {
    ctx.restore()
  }

  requestAnimationFrame(render)
}

function getCamera() {
  const targetX = myPos.value.x * TILE_SIZE - canvasWidth.value / 2
  const targetY = myPos.value.y * TILE_SIZE - canvasHeight.value / 2
  return {
    x: Math.max(0, Math.min(worldWidth.value - canvasWidth.value, targetX)),
    y: Math.max(0, Math.min(worldHeight.value - canvasHeight.value, targetY)),
  }
}

function renderMiniMap(camera) {
  if (!miniCtx || !mapData.value) return

  const w = miniMapWidth.value
  const h = miniMapHeight.value
  const scale = Math.min(w / worldWidth.value, h / worldHeight.value)
  const mapW = worldWidth.value * scale
  const mapH = worldHeight.value * scale
  const offsetX = (w - mapW) / 2
  const offsetY = (h - mapH) / 2

  miniCtx.clearRect(0, 0, w, h)
  miniCtx.fillStyle = '#080d18'
  miniCtx.fillRect(0, 0, w, h)

  miniCtx.save()
  miniCtx.translate(offsetX, offsetY)
  miniCtx.scale(scale, scale)

  floorTiles.value.forEach(({ x, y }) => {
    miniCtx.fillStyle = 'rgba(30, 41, 59, 0.95)'
    miniCtx.fillRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
  })

  walls.value.forEach(key => {
    const [x, y] = key.split(',').map(Number)
    miniCtx.fillStyle = 'rgba(2, 6, 23, 0.98)'
    miniCtx.fillRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
  })

  taskZones.value.forEach(zone => {
    const isAssigned = tasksAssigned.value.includes(zone.id)
    const isDone = completedTaskIds.value.includes(zone.id)
    if (!isAssigned && !isDone) return
    miniCtx.fillStyle = isDone ? '#94a3b8' : '#facc15'
    miniCtx.fillRect(zone.x * TILE_SIZE + 5, zone.y * TILE_SIZE + 5, TILE_SIZE - 10, TILE_SIZE - 10)
  })

  miniCtx.strokeStyle = 'rgba(250, 204, 21, 0.95)'
  miniCtx.lineWidth = 4 / scale
  miniCtx.strokeRect(camera.x, camera.y, canvasWidth.value, canvasHeight.value)

  const px = myPos.value.x * TILE_SIZE
  const py = myPos.value.y * TILE_SIZE
  miniCtx.fillStyle = '#38bdf8'
  miniCtx.beginPath()
  miniCtx.arc(px, py, 9 / scale, 0, Math.PI * 2)
  miniCtx.fill()
  miniCtx.strokeStyle = '#ffffff'
  miniCtx.lineWidth = 2 / scale
  miniCtx.stroke()

  miniCtx.restore()
}

function getMyId() {
  return myUserId.value
}

function getMyVisionRadius() {
  if (!myRole.value) return 5
  if (myRole.value === 'impostor') return 6
  if (!players.value['me']?.alive) return 8
  return 5
}

// Tasks
function tryStartTask() {
  if (myRole.value !== 'crewmate' || !mapData.value) return
  const zone = nearbyTask.value
  if (!zone) return
  if (!tasksAssigned.value.includes(zone.id)) return
  if (completedTaskIds.value.includes(zone.id)) return

  activeTask.value = { ...zone }
  wireStep.value = 0
  wireOptions.value = [...(zone.sequence || ['A', 'B', 'C', 'D'])]
  calibrateDone.value = 0
  taskProgress.value = 0

  if (props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'among_us_task_start',
      data: { task_id: zone.id }
    }))
  }
}

function startTaskHold() {
  if (!isTimedTask(activeTask.value) || taskHoldInterval) return
  taskHolding.value = true
  taskHoldInterval = setInterval(() => {
    const duration = Math.max(1, Number(activeTask.value?.duration || 3))
    taskProgress.value += 100 / (duration * 10)
    if (taskProgress.value >= 100) {
      completeHoldTask()
    }
  }, 100)
}

function stopTaskHold() {
  taskHolding.value = false
  if (taskHoldInterval) {
    clearInterval(taskHoldInterval)
    taskHoldInterval = null
  }
}

function completeHoldTask() {
  stopTaskHold()
  if (!activeTask.value) return
  if (props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'among_us_task_step',
      data: { task_id: activeTask.value.id }
    }))
  }
  activeTask.value = null
}

function isTimedTask(task) {
  return task && ['button_press', 'swipe_card', 'upload_data'].includes(task.type)
}

function clickWire(wire) {
  if (!activeTask.value) return
  const expected = activeTask.value.sequence[wireStep.value]
  if (wire === expected) {
    if (props.socket?.readyState === 1) {
      props.socket.send(JSON.stringify({
        type: 'among_us_task_step',
        data: { task_id: activeTask.value.id, step: wire }
      }))
    }
    wireStep.value++
    if (wireStep.value >= activeTask.value.sequence.length) {
      activeTask.value = null
    }
  } else {
    wireStep.value = 0
  }
}

function wireColor(wire) {
  const colors = { 'A': 'bg-red-500', 'B': 'bg-blue-500', 'C': 'bg-green-500', 'D': 'bg-yellow-500',
                   '1': 'bg-red-500', '2': 'bg-blue-500', '3': 'bg-green-500', '4': 'bg-yellow-500' }
  return colors[wire] || 'bg-gray-500'
}

function calibrateClick() {
  if (!activeTask.value) return
  calibrateDone.value++
  if (props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'among_us_task_step',
      data: { task_id: activeTask.value.id }
    }))
  }
  if (calibrateDone.value >= 3 && activeTask.value) {
    activeTask.value = null
  }
}

function cancelTask() {
  activeTask.value = null
  stopTaskHold()
}

// Kill
function sendKill() {
  if (myRole.value !== 'impostor' || killCooldown.value > 0) return
  // Find nearest crewmate
  const myId = getMyId()
  const myP = players.value[myId]
  if (!myP) return

  let nearest = null
  let nearestDist = Infinity
  Object.values(players.value).forEach(p => {
    if (p.id === myId || !p.alive) return
    const dist = Math.hypot(p.x - myP.x, p.y - myP.y)
    if (dist < nearestDist && dist <= 1.5) {
      nearest = p
      nearestDist = dist
    }
  })

  if (nearest && props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'among_us_kill',
      data: { target_id: nearest.id }
    }))
  }
}

function tryAutoKill() {
  sendKill()
}

// Report
function tryReport() {
  if (!mapData.value) return
  const myP = players.value[getMyId()]
  if (!myP) return

  const nearbyBody = deadBodies.value.find(b => {
    const dist = Math.hypot(b.x - myP.x, b.y - myP.y)
    return dist <= 1.0
  })

  if (nearbyBody && props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'among_us_report',
      data: {}
    }))
  }
}

function handleCanvasClick() {
  canvasEl.value?.focus()
}

// Sabotage
function sendSabotage() {
  if (myRole.value !== 'impostor') return
  if (props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'among_us_sabotage',
      data: { type: 'lights' }
    }))
  }
}

// Voting
function vote(targetId) {
  myVote.value = targetId
  if (props.socket?.readyState === 1) {
    props.socket.send(JSON.stringify({
      type: 'among_us_vote',
      data: { target_id: targetId }
    }))
  }
}

// WebSocket handlers
function handleAmongUsState(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  emit('session-running')

  players.value = {}
  data.players?.forEach(p => {
    players.value[p.id] = p
    playerNames.value[p.id] = p.display_name || p.id
    if (p.id === getMyId()) {
      myPos.value = { x: p.x, y: p.y }
    }
  })

  deadBodies.value = data.dead_bodies || []
  lightsOut.value = data.lights_out || false

  if (data.task_progress) {
    tasksCompleted.value = data.task_progress.done || 0
    tasksTotal.value = data.task_progress.total || 0
  }
}

function handleAmongUsEvent(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return

  const event = data.event
  if (event === 'kill') {
    // Kill happened
  } else if (event === 'task_complete') {
    tasksCompleted.value = data.progress?.done || tasksCompleted.value
    if (data.player_id === getMyId() && data.task_id && !completedTaskIds.value.includes(data.task_id)) {
      completedTaskIds.value.push(data.task_id)
    }
  } else if (event === 'sabotage' && data.type === 'lights') {
    lightsOut.value = data.active
  }
}

function handleRole(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  myRole.value = data.role
  if (data.tasks) {
    tasksAssigned.value = data.tasks
    completedTaskIds.value = []
  }
}

function handleMeetingStart(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  meetingState.value = {
    phase: 'discussion',
    reporter_id: data.reporter_id,
    victim_id: data.victim_id,
    participants: data.participants || [],
  }
  meetingTimer.value = data.discussion_seconds || 30
  myVote.value = null
  startMeetingTimer()
}

function handleMeetingVotePhase(data) {
  if (!meetingState.value) return
  meetingState.value.phase = 'voting'
  meetingTimer.value = data.voting_seconds || 15
  startMeetingTimer()
}

function handleMeetingResult(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  meetingState.value = null
  const ejectedId = data.ejected_id
  meetingResult.value = {
    ejected_id: ejectedId,
    ejected_name: playerNames.value[ejectedId] || ejectedId,
    ejected_was_impostor: players.value[ejectedId]?.role === 'impostor' || false,
    votes: data.votes || {},
    skipped: data.skipped,
  }
}

function handleGameOver(data) {
  if (props.sessionId && data.session_id && data.session_id !== props.sessionId) return
  gameOver.value = {
    winner: data.winner,
    impostors: data.impostors || [],
  }
}

let meetingTimerInterval = null
function startMeetingTimer() {
  if (meetingTimerInterval) clearInterval(meetingTimerInterval)
  meetingTimerInterval = setInterval(() => {
    if (meetingTimer.value > 0) {
      meetingTimer.value--
    } else {
      clearInterval(meetingTimerInterval)
    }
  }, 1000)
}

function onSocketMessage(event) {
  let message
  try { message = JSON.parse(event.data) } catch { return }

  if (message.type === 'among_us_state') handleAmongUsState(message.data)
  else if (message.type === 'among_us_event') handleAmongUsEvent(message.data)
  else if (message.type === 'among_us_role') handleRole(message.data)
  else if (message.type === 'meeting_start') handleMeetingStart(message.data)
  else if (message.type === 'meeting_vote_phase') handleMeetingVotePhase(message.data)
  else if (message.type === 'meeting_result') handleMeetingResult(message.data)
  else if (message.type === 'game_over') handleGameOver(message.data)
  else if (message.type === 'alive_count') {
    // handled by parent
  }
}

// Computed
const roleColorClass = computed(() => {
  return myRole.value === 'impostor' ? 'text-red-400' : 'text-green-400'
})

// Lifecycle
watch(() => props.socket, (s, prev) => {
  if (prev) prev.removeEventListener?.('message', onSocketMessage)
  if (s) s.addEventListener('message', onSocketMessage)
}, { immediate: true })

onMounted(async () => {
  await loadMap()
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('blur', resetMovementKeys)
  if (canvasEl.value) {
    ctx = canvasEl.value.getContext('2d')
    miniCtx = miniMapEl.value?.getContext('2d') || null
    canvasEl.value.focus()
    requestAnimationFrame(render)
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('blur', resetMovementKeys)
  if (props.socket) props.socket.removeEventListener?.('message', onSocketMessage)
  if (moveInterval) clearInterval(moveInterval)
  if (taskHoldInterval) clearInterval(taskHoldInterval)
  if (meetingTimerInterval) clearInterval(meetingTimerInterval)
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 300ms; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

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
</style>
