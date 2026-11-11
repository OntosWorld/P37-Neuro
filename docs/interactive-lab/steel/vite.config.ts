import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Relative base keeps the build embeddable beneath the existing Brain Lab without
// altering its GitHub Pages deployment or router.
export default defineConfig({
  plugins: [react()],
  base: './',
  server: { port: 5173, host: '0.0.0.0' },
  build: { outDir: 'dist', emptyOutDir: true },
});
