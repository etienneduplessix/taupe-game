<template>
  <label class="flex flex-col gap-1">
    <span class="font-arcade text-[10px] text-amber-300">{{ label.toUpperCase() }}</span>
    <input
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.type === 'number' ? parseFloat($event.target.value) : $event.target.value)"
      type="number"
      :step="step"
      class="p-2 bg-[#1a0f08] text-amber-100 border-2 border-amber-400/40 rounded-lg font-mono focus:border-amber-400 focus:outline-none"
    />
  </label>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  modelValue: { type: [Number, String], default: 0 },
  step: { type: [Number, String], default: 1 },
})
defineEmits(['update:modelValue'])
</script>
