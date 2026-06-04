<template>
  <div class="relative min-h-screen flex items-center justify-center p-6">
    <div class="panel-3d p-8 max-w-sm w-full">
      <h2 class="title-3d text-2xl mb-6 text-center">🧪 DEV LOGIN</h2>
      <form @submit.prevent="login" class="flex flex-col gap-4">
        <Field label="Display name" v-model="displayName" />
        <button type="submit" class="btn-3d btn-primary !py-3">
          Sign In
        </button>
      </form>
      <div v-if="error" class="mt-4 text-red-400 font-arcade text-[10px] text-center">{{ error }}</div>

      <div class="mt-6 border-t border-amber-400/20 pt-4">
        <div class="font-arcade text-[9px] text-amber-300 mb-3 text-center">QUICK ADD</div>
        <div class="grid grid-cols-2 gap-2">
          <button v-for="name in quickNames" :key="name" @click="quickLogin(name)" class="btn-3d btn-ghost !py-1.5 !text-[10px]">{{ name }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const displayName = ref('')
const error = ref('')
const quickNames = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank']

async function doLogin(name) {
  error.value = ''
  try {
    const data = await $fetch('/api/auth/debug/login', {
      method: 'POST',
      body: { display_name: name },
    })
    if (data) {
      await $fetch('/api/me', { credentials: 'include' })
      navigateTo('/')
    }
  } catch (e) {
    error.value = e.data?.detail || 'Login failed'
  }
}

function login() {
  if (!displayName.value.trim()) return
  doLogin(displayName.value.trim())
}

function quickLogin(name) {
  doLogin(name)
}
</script>
