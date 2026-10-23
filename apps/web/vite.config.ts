import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { offlineApp } from './pwa';

export default defineConfig({
  plugins: [react(), offlineApp()],
});
