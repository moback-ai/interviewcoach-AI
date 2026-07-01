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
  const apexDomain = env.VITE_APEX_DOMAIN || 'ugaanlabs.ai'
  const canonicalHost = env.VITE_CANONICAL_HOST || `www.${apexDomain}`

  return {
    plugins: [react(), tailwindcss()],
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-router-dom',
        'framer-motion',
        'react-syntax-highlighter',
        'react-syntax-highlighter/dist/esm/styles/prism',
      ],
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      minify: 'esbuild',
      esbuild: {
        drop: isDev ? ['debugger'] : ['console', 'debugger'],
      },
      chunkSizeWarningLimit: 1000,
      sourcemap: false,
      // Avoid manualChunks for libs used across many lazy routes (react, framer-motion,
      // recharts, syntax-highlighter). Isolating them hoists Vite's route loader and
      // React into a vendor chunk, which breaks /login until that chunk loads.
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
      'import.meta.env.VITE_STORAGE_URL': JSON.stringify(storageUrl),
      'import.meta.env.VITE_APEX_DOMAIN': JSON.stringify(apexDomain),
      'import.meta.env.VITE_CANONICAL_HOST': JSON.stringify(canonicalHost),
    },
  }
})
