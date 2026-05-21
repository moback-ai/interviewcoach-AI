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
        drop: ['debugger'],
      },
      chunkSizeWarningLimit: 1000,
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) {
              return;
            }
            if (id.includes('monaco-editor') || id.includes('@monaco-editor')) {
              return 'monaco';
            }
            if (id.includes('recharts')) {
              return 'recharts';
            }
            if (id.includes('framer-motion')) {
              return 'framer-motion';
            }
            if (id.includes('react-syntax-highlighter') || id.includes('prismjs')) {
              return 'syntax-highlighter';
            }
            if (id.includes('socket.io-client')) {
              return 'socket-io';
            }
            if (id.includes('swiper')) {
              return 'swiper';
            }
            if (id.includes('three')) {
              return 'three';
            }
            if (id.includes('vanta')) {
              return 'vanta';
            }
            if (id.includes('react-dom')) {
              return 'react-dom';
            }
            if (id.includes('react')) {
              return 'react';
            }
          },
        },
      },
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
    },
  }
})
