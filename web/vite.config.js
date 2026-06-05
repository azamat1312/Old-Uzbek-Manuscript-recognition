import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev rejimida (npm run dev) frontend 5173-portda ishlaydi va /api so'rovlarini
// 8000-portdagi FastAPI backendiga uzatadi (proxy). Build qilinganda esa
// (npm run build) natija web/dist ga chiqadi va uni FastAPI o'zi tarqatadi.
export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
