import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const frontendPort = process.env.CATALYST_FRONTEND_PORT
  ? parseInt(process.env.CATALYST_FRONTEND_PORT, 10)
  : 8939;

const backendPort = process.env.CATALYST_PORT || "8139";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: frontendPort,
  },
  define: {
    'import.meta.env.CATALYST_PORT': JSON.stringify(backendPort),
  },
})
