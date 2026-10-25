import { createApp } from "vue";
import { createPinia } from "pinia";
import { VueQueryPlugin } from "@tanstack/vue-query";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";
import "./styles/tokens.scss";
import "./styles/element-theme.scss";
import App from "./app/App.vue";
import { router } from "./app/router";
import "./styles/main.scss";
import "./styles/discovery.scss";
import { initCsrf } from "./api/client";
createApp(App)
  .use(createPinia())
  .use(VueQueryPlugin, {
    queryClientConfig: {
      defaultOptions: {
        queries: { staleTime: 15000, refetchOnWindowFocus: false, retry: 1 },
      },
    },
  })
  .use(ElementPlus, { locale: zhCn })
  .use(router)
  .mount("#app");

void initCsrf().catch((error) =>
  console.error(error instanceof Error ? error.message : "CSRF初始化失败"),
);
