<template>
  <div class="relative min-h-screen scanlines overflow-hidden">
    <Scene />

    <div class="relative z-10 p-4 md:p-8 max-w-3xl mx-auto">
      <header class="flex justify-between items-center mb-8 gap-4">
        <div class="flex items-center gap-4">
          <NuxtLink to="/admin" class="btn-3d btn-secondary !py-2 !px-4">
            <span class="text-xl">←</span>
            Back
          </NuxtLink>
          <h1 class="title-3d text-2xl md:text-4xl">CONFIGURE</h1>
        </div>
      </header>

      <div v-if="loading" class="text-center py-16 font-arcade text-amber-200 animate-pulse">
        LOADING...
      </div>

      <div v-else-if="!session" class="panel-3d p-8 text-center">
        <div class="text-5xl mb-3">❓</div>
        <p class="font-display text-amber-100">Session not found</p>
      </div>

      <form v-else @submit.prevent="save" class="panel-3d p-6 md:p-8 flex flex-col gap-5">
        <div>
          <div class="font-arcade text-[10px] text-amber-300 mb-1">SESSION</div>
          <div class="font-display text-2xl text-amber-100">{{ session.name }}</div>
          <div class="mt-1 inline-block font-arcade text-[9px] uppercase px-2 py-1 rounded" :class="statusClass">
            {{ session.status }}
          </div>
        </div>

        <div class="border-t border-amber-400/20 pt-5">
          <h2 class="font-display text-lg text-amber-100 mb-4">⚙️ Game Parameters</h2>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Base spawn interval (ms)" v-model.number="config.base_spawn_interval_ms" />
            <Field label="Min spawn interval (ms)" v-model.number="config.min_spawn_interval_ms" />
            <Field label="Base timeout (ms)" v-model.number="config.base_timeout_ms" />
            <Field label="Min timeout (ms)" v-model.number="config.min_timeout_ms" />
            <Field label="Scaling exponent" v-model.number="config.scaling_exponent" step="0.1" />
            <Field label="Miss penalty" v-model.number="config.miss_penalty" />
            <Field label="Max mistakes" v-model.number="config.max_mistakes" />
            <Field label="Speed window size" v-model.number="config.speed_window_size" />
            <Field label="Max avg latency (ms)" v-model.number="config.max_avg_latency_ms" />
          </div>

          <div class="mt-4">
            <div class="font-arcade text-[10px] text-amber-300 mb-2">ALLOWED KEYS</div>
            <input
              v-model="config.allowed_keys"
              type="text"
              class="w-full p-3 bg-[#1a0f08] text-amber-100 border-2 border-amber-400/60 rounded-lg font-mono focus:border-amber-400 focus:outline-none uppercase tracking-widest"
            />
          </div>

          <div class="mt-4">
            <div class="font-arcade text-[10px] text-amber-300 mb-2">KEYBOARD LAYOUT</div>
            <div class="flex gap-2">
              <button
                v-for="opt in ['QWERTY', 'AZERTY', 'NUMPAD']"
                :key="opt"
                type="button"
                @click="config.keyboard_layout = opt"
                :class="['btn-3d', 'flex-1', '!py-2', '!text-xs', (config.keyboard_layout || 'QWERTY') === opt ? 'btn-primary' : 'btn-ghost']"
              >
                {{ opt }}
              </button>
            </div>
            <div v-if="config.keyboard_layout === 'NUMPAD'" class="font-arcade text-[8px] text-amber-300/70 mt-2">
              Numpad maps digits 7-9/4-6/1-3/0 → A-J. Restrict ALLOWED KEYS to ABCDEFGHIJ to match.
            </div>
          </div>

          <label class="flex items-center gap-3 mt-4 cursor-pointer">
            <input v-model="config.timeouts_count_as_mistakes" type="checkbox" class="w-5 h-5 accent-amber-400" />
            <span class="font-display text-amber-100">Timeouts count as mistakes</span>
          </label>
        </div>

        <div v-if="saved" class="font-arcade text-[10px] text-green-300 text-center animate-mole-pop">
          ✓ SAVED!
        </div>

        <div class="flex gap-3 justify-end border-t border-amber-400/20 pt-5">
          <NuxtLink to="/admin" class="btn-3d btn-secondary !py-2 !px-4">Cancel</NuxtLink>
          <button type="submit" class="btn-3d btn-primary !py-2 !px-4">
            <span>💾</span> Save
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import Scene from '~/components/Scene.vue'

definePageMeta({ middleware: 'admin' })

const runtimeConfig = useRuntimeConfig()
const API = runtimeConfig.public.apiBase
const route = useRoute()

const session = ref(null)
const config = ref({})
const loading = ref(true)
const saved = ref(false)

const statusClass = computed(() => ({
  'waiting': 'bg-yellow-500/30 text-yellow-200 border border-yellow-400/60',
  'running': 'bg-green-500/30 text-green-200 border border-green-400/60',
  'ended': 'bg-gray-500/30 text-gray-200 border border-gray-400/40',
}[session.value?.status] || ''))

const fetchSession = async () => {
  loading.value = true
  try {
    const data = await $fetch(`${API}/admin/sessions/${route.params.id}`, { credentials: 'include' })
    session.value = data
    config.value = { ...data.config_json }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const save = async () => {
  try {
    await $fetch(`${API}/admin/sessions/${route.params.id}`, {
      method: 'PUT',
      credentials: 'include',
      body: { config: config.value }
    })
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (e) {
    alert('Error saving: ' + (e.data?.detail || e.message))
  }
}

onMounted(fetchSession)
</script>
