import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }: { mode: string }) => {
  const env = loadEnv(mode, '.', 'VITE_');
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: env['VITE_API_URL'] ?? 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api/, ''),
        },
      },
    },
  };
});
