<template>
  <div class="relative min-h-screen scanlines overflow-hidden">
    <Scene />

    <!-- Cute moles peeking at the bottom -->
    <div class="fixed bottom-[14%] left-[8%] text-5xl animate-mole-bob drop-shadow-[0_6px_8px_rgba(0,0,0,0.6)] pointer-events-none">🐹</div>
    <div class="fixed bottom-[18%] right-[10%] text-6xl animate-mole-bob drop-shadow-[0_6px_8px_rgba(0,0,0,0.6)] pointer-events-none" style="animation-delay: -0.4s;">🐹</div>
    <div class="fixed bottom-[10%] left-[55%] text-4xl animate-mole-bob drop-shadow-[0_6px_8px_rgba(0,0,0,0.6)] pointer-events-none" style="animation-delay: -0.8s;">🐹</div>

    <div class="fixed inset-0 z-10 flex flex-col items-center justify-center p-4 md:p-6">
      <div class="absolute top-16 text-center animate-float">
        <h1 class="title-3d text-4xl md:text-6xl leading-none">TAUPE<br/>TYPING</h1>
        <p class="font-arcade text-[9px] md:text-xs text-amber-200/80 tracking-[0.3em] mt-3">
          WHACK · TYPE · SURVIVE
        </p>
      </div>

      <div class="panel-3d p-8 max-w-md w-full text-center">
        <p class="text-purple-100 mb-7 font-display text-lg leading-snug">
          Last typer standing wins.<br/>
          <span class="text-amber-300 font-bold">Are you fast enough?</span>
        </p>

        <button @click="login" class="btn-3d btn-primary w-full">
          <span class="text-2xl">🎮</span>
          Login with 42
        </button>

        <p v-if="error" class="mt-4 text-red-400 text-sm animate-shake font-semibold">{{ error }}</p>

        <p class="mt-6 text-[10px] text-purple-300/60 uppercase tracking-widest font-arcade">
          School LAN · QWERTY
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import Scene from '~/components/Scene.vue'
const config = useRuntimeConfig()
const error = ref(null)
const login = async () => {
  try {
    const response = await $fetch(`${config.public.apiBase}/auth/login`)
    if (response.url) window.location.href = response.url
  } catch (e) { error.value = 'Login failed. Please try again.' }
}
</script>
