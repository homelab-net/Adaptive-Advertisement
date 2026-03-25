import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8004',
        changeOrigin: true,
      },
      '/healthz': { target: 'http://localhost:8004', changeOrigin: true },
      '/readyz':  { target: 'http://localhost:8004', changeOrigin: true },
    },
  },
})
