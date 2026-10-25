import { defineConfig } from 'vitest/config';
import { loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
export default defineConfig(({mode})=>({
  plugins:[vue()],
  server:{proxy:{'/api':loadEnv(mode,'.','').VITE_API_TARGET||'http://127.0.0.1:8000'}},
  test:{environment:'jsdom'},
  build:{rollupOptions:{output:{manualChunks:{vue:['vue','vue-router','pinia','@tanstack/vue-query'],element:['element-plus']}}}},
}));
