<template>
  <div class="panel-3d p-5 md:p-6 select-none" ref="keyboardContainer">
    <div class="flex flex-col gap-2">
      <div v-for="(row, rowIndex) in layout" :key="rowIndex" class="flex justify-center gap-1.5 md:gap-2" :style="{ paddingLeft: rowIndex * 18 + 'px' }">
        <div
          v-for="key in row"
          :key="key"
          :ref="el => { keyRefs[key] = el }"
          :class="[
            'keycap-3d',
            activeKey === key ? 'keycap-active' : '',
            wrongKey === key ? 'keycap-wrong animate-shake' : '',
            pressedKeys.has(key) && activeKey !== key ? 'keycap-pressed' : ''
          ]"
          @mousedown="handleKeyPress(key)"
        >
          {{ key }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  activeKey: { type: String, default: null },
  wrongKey: { type: String, default: null }
})

const emit = defineEmits(['key-press'])

const layout = [
  ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
  ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
  ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
  ['Z', 'X', 'C', 'V', 'B', 'N', 'M']
]

const keyboardContainer = ref(null)
const keyRefs = reactive({})
const pressedKeys = ref(new Set())

const keyDownHandler = (e) => {
  const key = e.key.toUpperCase()
  if (layout.flat().includes(key)) {
    pressedKeys.value.add(key)
    emit('key-press', key)
  }
}
const keyUpHandler = (e) => {
  pressedKeys.value.delete(e.key.toUpperCase())
}

function handleKeyPress(key) { emit('key-press', key) }

function getKeyPosition(key) {
  const keyEl = keyRefs[key]
  if (!keyEl) return null
  const rect = keyEl.getBoundingClientRect()
  const containerRect = keyboardContainer.value?.getBoundingClientRect()
  if (!containerRect) return null
  return {
    x: rect.left - containerRect.left + rect.width / 2,
    y: rect.top - containerRect.top,
    width: rect.width,
    height: rect.height
  }
}

defineExpose({ getKeyPosition })

onMounted(() => {
  window.addEventListener('keydown', keyDownHandler)
  window.addEventListener('keyup', keyUpHandler)
})
onUnmounted(() => {
  window.removeEventListener('keydown', keyDownHandler)
  window.removeEventListener('keyup', keyUpHandler)
})
</script>
