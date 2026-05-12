export default defineNuxtRouteMiddleware(async () => {
  try {
    const me = await $fetch('/api/me', { credentials: 'include' })
    if (!me) return navigateTo('/login')
    if (!me.is_admin) return navigateTo('/')
  } catch (e) {
    return navigateTo('/login')
  }
})
