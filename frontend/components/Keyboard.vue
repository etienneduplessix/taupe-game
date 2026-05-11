<template>
  <div class="panel-3d p-5 md:p-6 select-none" ref="keyboardContainer">
    <div class="flex flex-col gap-2" :class="props.layout === 'NUMPAD' ? 'items-center' : ''">
      <div
        v-for="(row, rowIndex) in rows"
        :key="rowIndex"
        class="flex justify-center gap-1.5 md:gap-2"
        :style="props.layout === 'NUMPAD' ? {} : { paddingLeft: rowIndex * 18 + 'px' }"
      >
        <div
          v-for="key in row"
          :key="key"
          :ref="el => { keyRefs[key] = el }"
          :class="[
            'keycap-3d cursor-default',
            activeKey === key ? 'keycap-active' : '',
            wrongKey === key ? 'keycap-wrong animate-shake' : '',
            pressedKeys.has(key) && activeKey !== key ? 'keycap-pressed' : ''
          ]"
        >
          <span>{{ key }}</span>
          <span
            v-if="props.layout === 'NUMPAD' && numpadDigitForLetter(key)"
            class="absolute top-0.5 right-1 font-arcade text-[7px] text-amber-300/80"
          >{{ numpadDigitForLetter(key) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  activeKey: { type: String, default: null },
  wrongKey: { type: String, default: null },
  layout: { type: String, default: 'QWERTY' }
})

const emit = defineEmits(['key-press'])

const LAYOUTS = {
  QWERTY: [
    ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
    ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
    ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
    ['Z', 'X', 'C', 'V', 'B', 'N', 'M']
  ],
  AZERTY: [
    ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
    ['A', 'Z', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
    ['Q', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'M'],
    ['W', 'X', 'C', 'V', 'B', 'N']
  ],
  NUMPAD: [
    ['A', 'B', 'C'],
    ['D', 'E', 'F'],
    ['G', 'H', 'I'],
    ['J']
  ]
}

// Physical Numpad digit → letter (for keydown translation in NUMPAD mode)
const NUMPAD_DIGIT_TO_LETTER = {
  '7': 'A', '8': 'B', '9': 'C',
  '4': 'D', '5': 'E', '6': 'F',
  '1': 'G', '2': 'H', '3': 'I',
  '0': 'J'
}
const NUMPAD_LETTER_TO_DIGIT = Object.fromEntries(
  Object.entries(NUMPAD_DIGIT_TO_LETTER).map(([d, l]) => [l, d])
)

function numpadDigitForLetter(letter) {
  return NUMPAD_LETTER_TO_DIGIT[letter] || ''
}

const rows = computed(() => LAYOUTS[props.layout] || LAYOUTS.QWERTY)
const flatKeys = computed(() => new Set(rows.value.flat()))

const keyboardContainer = ref(null)
const keyRefs = reactive({})
const pressedKeys = ref(new Set())

function translateEvent(e) {
  if (props.layout === 'NUMPAD' && /^Numpad[0-9]$/.test(e.code)) {
    const digit = e.code.slice(6)
    return NUMPAD_DIGIT_TO_LETTER[digit] || null
  }
  return e.key.toUpperCase()
}

const keyDownHandler = (e) => {
  const key = translateEvent(e)
  if (key && flatKeys.value.has(key)) {
    pressedKeys.value.add(key)
    emit('key-press', key)
  }
}
const keyUpHandler = (e) => {
  const key = translateEvent(e)
  if (key) pressedKeys.value.delete(key)
}

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

<style scoped>
.keycap-3d {
  position: relative;
}
</style>
