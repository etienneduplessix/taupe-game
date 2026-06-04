export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  modules: ['@pinia/nuxt'],
  postcss: {
    plugins: {
      "@tailwindcss/postcss": {},
      autoprefixer: {},
    },
  },
  srcDir: '.',
  vite: {
    server: {
      hmr: {
        clientPort: 8080,
        port: 24678,
        protocol: 'ws',
      },
    },
  },
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8080/api',
      wsBase: process.env.NUXT_PUBLIC_WS_BASE || 'ws://localhost:8080/ws',
    },
  },
})
