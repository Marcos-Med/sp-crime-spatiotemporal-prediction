import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' deixa o site funcionar em qualquer subpasta (GitHub Pages, Netlify, etc.)
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    chunkSizeWarningLimit: 4000,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/app.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
});
