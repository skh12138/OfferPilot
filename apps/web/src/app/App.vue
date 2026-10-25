<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import PendingRuns from "../components/PendingRuns.vue";
import NavIcon from "../components/NavIcon.vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";
import { useSession } from "./session";
import { useAction } from "./action";
import { useUi } from "./ui";
import { client, unwrap } from "../api/client";
const session = useSession(),
  router = useRouter(),
  route = useRoute(),
  cache = useQueryClient(),
  ui = useUi();
const navigation = [
  { path: "/today", name: "今日", icon: "today" },
  { path: "/discover", name: "找岗位", icon: "discover" },
  { path: "/jobs", name: "岗位库", icon: "jobs" },
  { path: "/applications", name: "我的申请", icon: "applications" },
  { path: "/study", name: "面试准备", icon: "study" },
  { path: "/profile", name: "我的资料", icon: "profile" },
  { path: "/reviews", name: "复盘与 Offer", icon: "reviews" },
];
const links = computed(() =>
  session.user?.is_admin
    ? [
        ...navigation,
        { path: "/operations", name: "来源与运营", icon: "operations" },
      ]
    : navigation,
);
const current = computed(
  () =>
    links.value.find((n) => route.path.startsWith(n.path))?.name ??
    (session.user ? "工作空间" : "登录"),
);
const menu = ref(false);
const cap = useQuery({
  queryKey: ["capabilities"],
  queryFn: async () => unwrap(await client.GET("/api/v1/capabilities")),
});
watch(
  () => route.fullPath,
  () => {
    menu.value = false;
  },
);
watch(
  () => session.user?.id,
  (id, previous) => {
    if (previous && id !== previous) {
      cache.clear();
      ui.clear();
      menu.value = false;
    }
  },
);
const { busy: logoutBusy, error: logoutError, act: logoutAct } = useAction();
async function logout() {
  await logoutAct(async () => {
    if (ui.dirty) {
      try {
        await ElMessageBox.confirm(
          "退出会清除本次会话中尚未提交的草稿。",
          "退出登录？",
          {
            confirmButtonText: "放弃草稿并退出",
            cancelButtonText: "继续编辑",
            type: "warning",
          },
        );
      } catch {
        return;
      }
    }
    await session.logout();
    ui.clear();
    cache.clear();
    await router.push("/login");
  });
}
function unload(event: BeforeUnloadEvent) {
  if (ui.dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
}
function expired() {
  session.user = undefined;
  ui.clear();
  cache.clear();
  void router.replace("/login");
}
onMounted(() => {
  window.addEventListener("beforeunload", unload);
  window.addEventListener("offerpilot:session-expired", expired);
});
onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", unload);
  window.removeEventListener("offerpilot:session-expired", expired);
});
</script>
<template>
  <a href="#workspace-content" class="sr-only">跳到主要内容</a>
  <div class="app-shell" :class="{ anonymous: !session.user }">
    <aside v-if="session.user" class="app-sidebar">
      <RouterLink class="brand" to="/today"
        ><span class="brand-mark">O</span>OfferPilot</RouterLink
      >
      <p class="aside-note">每一步，都有依据。</p>
      <nav class="app-nav" aria-label="主要导航">
        <RouterLink v-for="link in links" :key="link.path" :to="link.path"
          ><NavIcon :name="link.icon" /><span>{{ link.name }}</span></RouterLink
        >
      </nav>
      <div class="account">
        <span>{{ session.user.username }}</span
        ><el-button link :loading="logoutBusy" @click="logout"
          >退出登录</el-button
        >
      </div>
    </aside>
    <div class="workspace">
      <header class="app-topbar">
        <div class="toolbar" style="margin: 0">
          <el-button
            v-if="session.user"
            class="mobile-menu"
            text
            aria-label="打开导航"
            @click="menu = true"
            ><NavIcon name="menu" /></el-button
          ><span
            ><span class="breadcrumb-home">工作空间 / </span>{{ current }}</span
          >
        </div>
        <div class="app-topbar-actions">
          <el-tag
            :type="cap.data.value?.mode === 'live' ? 'success' : 'info'"
            >{{
              !cap.data.value
                ? "读取环境中"
                : cap.data.value.mode === "live"
                  ? "真实模式"
                  : "演示数据 / 未联网"
            }}</el-tag
          ><el-button
            v-if="session.user"
            class="mobile-logout"
            text
            :loading="logoutBusy"
            @click="logout"
            >退出登录</el-button
          >
        </div>
      </header>
      <main id="workspace-content" class="app-main">
        <el-alert
          v-if="logoutError"
          :title="logoutError"
          type="error"
        /><PendingRuns v-if="session.user" /><RouterView :key="route.path" />
      </main>
      <footer class="app-footer">
        资料默认私有 · 外网投递与录用结果由本人确认 · Asia/Shanghai
      </footer>
    </div>
  </div>
  <el-drawer
    v-model="menu"
    title="工作空间导航"
    direction="ltr"
    size="min(85%, 300px)"
    ><nav class="app-nav" aria-label="移动导航">
      <RouterLink v-for="link in links" :key="link.path" :to="link.path"
        ><NavIcon :name="link.icon" />{{ link.name }}</RouterLink
      >
    </nav>
    <p class="muted">{{ session.user?.username }}</p>
    <el-button :loading="logoutBusy" @click="logout"
      >退出登录</el-button
    ></el-drawer
  >
</template>
