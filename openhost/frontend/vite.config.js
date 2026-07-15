import { defineConfig } from 'vite';

export default defineConfig({
  base: '/openhost/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
