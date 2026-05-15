import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config — port 5173, proxy /api in dev only.
// In production, set VITE_BACKEND_URL to the backend's URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
