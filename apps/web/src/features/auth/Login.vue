<script setup lang="ts">
import { reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import { client, initCsrf, unwrap } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
const form = reactive({ username: "", password: "" }),
  session = useSession(),
  router = useRouter(),
  { busy, error, act } = useAction();
onMounted(() => act(initCsrf));
async function login() {
  await act(async () => {
    session.user = unwrap(
      await client.POST("/api/v1/auth/login", { body: form }),
    );
    await router.push("/jobs");
  });
}
</script>
<template>
  <section class="panel login-panel">
    <div class="brand"><span class="brand-mark">O</span>OfferPilot</div>
    <h1 style="margin-top: 32px">继续你的下一步</h1>
    <p class="subtitle">发现机会，记录进展，为面试做好准备。</p>
    <el-form label-position="top" @submit.prevent="login"
      ><el-form-item label="用户名"
        ><el-input
          v-model="form.username"
          autocomplete="username"
          aria-label="用户名" /></el-form-item
      ><el-form-item label="密码"
        ><el-input
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          aria-label="密码"
          show-password /></el-form-item
      ><el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
      /><el-button
        type="primary"
        native-type="submit"
        :loading="busy"
        style="width: 100%"
        >登录</el-button
      ></el-form
    >
    <p class="muted">账户由管理命令创建。演示账户需要显式执行 seed-demo。</p>
  </section>
</template>
