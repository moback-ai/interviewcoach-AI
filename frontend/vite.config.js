import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path';
import { loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file from frontend directory
  const env = loadEnv(mode, path.resolve(__dirname), '')
  
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    // ⚡ PERFORMANCE OPTIMIZATIONS
    build: {
      // Use esbuild for faster minification (already included with Vite)
      minify: 'esbuild',
      // Remove console.logs in production
      esbuild: {
        drop: ['console', 'debugger'],
      },
      // Code splitting - split vendor chunks
      rollupOptions: {
        output: {
          manualChunks: {
            // Separate large libraries into their own chunks
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'supabase-vendor': ['@supabase/supabase-js'],
            'ui-vendor': ['framer-motion', 'recharts', 'lucide-react'],
            'utils-vendor': ['jspdf', 'jspdf-autotable', 'prismjs'],
          },
        },
      },
      // Chunk size warnings
      chunkSizeWarningLimit: 1000,
      // Source maps for production (optional, remove for smaller builds)
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
      // Map Supabase variables to VITE_ prefixed versions for frontend
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(env.SUPABASE_URL || env.VITE_SUPABASE_URL),
      'import.meta.env.VITE_SUPABASE_ANON_KEY': JSON.stringify(env.SUPABASE_ANON_KEY || env.VITE_SUPABASE_ANON_KEY),
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(env.VITE_API_BASE_URL),
    }
  }
})
