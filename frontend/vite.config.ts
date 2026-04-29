import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    port: 5174,
    hmr: { overlay: false },
    proxy: {
      '/api': {
        target: `http://localhost:${process.env.BACKEND_PORT || '8001'}`,
        changeOrigin: true,
      },
      '/audio': {
        target: `http://localhost:${process.env.BACKEND_PORT || '8001'}`,
        changeOrigin: true,
      },
      '/images': {
        target: `http://localhost:${process.env.BACKEND_PORT || '8001'}`,
        changeOrigin: true,
      },
    },
  },
})
