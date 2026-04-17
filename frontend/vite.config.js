import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname), '')
  const isDev = mode === 'development'
  const apiBaseUrl = env.VITE_API_BASE_URL || (isDev ? 'http://localhost:5000/api' : '/api')
  const legacyBaseUrl = apiBaseUrl.replace(/\/api\/?$/, '')
  const storageUrl = env.VITE_STORAGE_URL || (isDev ? `${legacyBaseUrl}/storage` : '/storage')

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      minify: 'esbuild',
      esbuild: {
        drop: ['console', 'debugger'],
      },
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'ui-vendor': ['framer-motion', 'recharts', 'lucide-react'],
            'utils-vendor': ['jspdf', 'jspdf-autotable', 'prismjs'],
          },
        },
      },
      chunkSizeWarningLimit: 1000,
      sourcemap: false,
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      cors: true,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
      },
    },
    define: {
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(apiBaseUrl),
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(legacyBaseUrl),
      'import.meta.env.VITE_STORAGE_URL': JSON.stringify(storageUrl),
    },
  }
})
