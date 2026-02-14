import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api': 'http://localhost:8080'
    }
  },
  build: {
    outDir: path.resolve(__dirname, '../internal/web/static'),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('/@tanstack/')) return 'tanstack'
          return 'vendor'
        }
      }
    }
  }
})
