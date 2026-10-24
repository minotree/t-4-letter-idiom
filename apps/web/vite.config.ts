import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { offlineApp } from './pwa';

export default defineConfig(({ mode }) => ({
  plugins: [react(), offlineApp()],
  // Vercel's outputDirectory is relative to the repository root.
  build: mode === 'vercel' ? { outDir: '../../dist', emptyOutDir: true } : {},
}));
