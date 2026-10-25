<script setup lang="ts">
import DraftDrawer from "../../components/DraftDrawer.vue";
import { useDraft } from "../../app/ui";
import { useChoiceQuery, useListPosition } from "../../app/navigation";
import { formatDate } from "../../utils/dates";
import { computed, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { useRoute, useRouter } from "vue-router";
import { client, unwrap, key } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
const session = useSession(),
  route = useRoute(),
  router = useRouter(),
  { busy, error, act } = useAction(),
  show = ref(false),
  view = useChoiceQuery("view", ["list", "board"], "list");
const stage = computed({
  get: () => String(route.query.stage ?? ""),
  set: (stage) => {
    void router.replace({
      query: { ...route.query, stage: stage || undefined, cursor: undefined },
    });
  },
});
const labels: Record<string, string> = {
  interested: "意向",
  preparing: "准备投递",
  submitted: "已投递",
  assessment: "考核中",
  offer: "Offer 沟通",
  onboarding: "已接受 / 入职",
  closed: "已结束",
};
const apps = useQuery({
  queryKey: computed(() => [
    "applications",
    session.user?.id,
    stage.value,
    route.query.cursor,
  ]),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/applications", {
        params: {
          query: {
            stage: stage.value || undefined,
            limit: 100,
            cursor: route.query.cursor ? String(route.query.cursor) : undefined,
          },
        },
      }),
    ),
});
const creation = useDraft("application-create", () => ({
  title: "",
  company: "",
  job_url: "",
  apply_url: "",
  progress_url: "",
  navigation_hint: "",
}));
const draft = creation.draft;
useListPosition(computed(() => !apps.isPending.value));
const grouped = computed(() =>
  Object.keys(labels).map((stage) => ({
    stage,
    title: labels[stage],
    items: apps.data.value?.items.filter((a) => a.stage === stage) ?? [],
  })),
);
async function create() {
  await act(async () => {
    const app = unwrap(
      await client.POST("/api/v1/applications", {
        body: {
          ...draft.value,
          allow_reapply: false,
          job_url: draft.value.job_url || null,
          apply_url: draft.value.apply_url || null,
          progress_url: draft.value.progress_url || null,
        },
        headers: key(),
      }),
    );
    creation.saved();
    await router.push("/applications/" + app.id);
  });
}
</script>
<template>
  <h1>我的申请</h1>
  <p class="subtitle">每次真实申请一份档案。下一步与历史材料，随时可回查。</p>
  <div class="toolbar">
    <el-select
      v-model="stage"
      placeholder="全部阶段"
      clearable
      style="width: 180px"
      ><el-option
        v-for="(label, value) in labels"
        :key="value"
        :label="label"
        :value="value" /></el-select
    ><el-radio-group v-model="view"
      ><el-radio-button value="list">列表</el-radio-button
      ><el-radio-button value="board">看板</el-radio-button></el-radio-group
    ><el-button type="primary" @click="show = true"
      >补录申请 / 已有面试</el-button
    >
  </div>
  <el-alert v-if="error" type="error" :title="error" /><el-skeleton
    v-if="apps.isPending.value"
    animated
  /><el-alert
    v-if="apps.error.value"
    title="加载失败，请重试"
    type="error"
  /><el-button v-if="apps.error.value" @click="apps.refetch()"
    >重新加载申请</el-button
  >
  <p
    v-if="
      !apps.isPending.value &&
      !apps.error.value &&
      !apps.data.value?.items.length
    "
    class="panel empty"
  >
    还没有申请。可以从岗位加入，也可以直接补录已有面试。
  </p>
  <p class="muted">
    当前已加载 {{ apps.data.value?.items.length ?? 0 }} 条申请，不代表全部记录。
  </p>
  <div v-if="stage" class="filter-chips">
    <el-tag closable @close="stage = ''">阶段：{{ labels[stage] }}</el-tag
    ><el-button text @click="stage = ''">清空筛选</el-button>
  </div>
  <div v-if="view === 'list'" class="application-list">
    <article
      v-for="app in apps.data.value?.items"
      :key="app.id"
      class="flat-row"
    >
      <div class="row-top">
        <h2>
          <RouterLink :to="'/applications/' + app.id"
            >{{ app.company }} · {{ app.title }}</RouterLink
          >
        </h2>
        <el-tag>{{ labels[app.stage] }}</el-tag>
      </div>
      <div class="row-meta">
        <span>{{ app.company_status_raw || "企业原文状态未记录" }}</span
        ><span
          >本人最近核对：{{
            app.last_checked_at ? formatDate(app.last_checked_at) : "尚未核对"
          }}</span
        >
      </div>
    </article>
  </div>
  <template v-else
    ><p class="scroll-hint">
      按现有阶段分组；左右滚动查看各列，阶段只通过本人记录更新。
    </p>
    <div
      class="application-board local-scroll"
      aria-label="申请阶段看板"
      tabindex="0"
    >
      <section
        v-for="group in grouped"
        :key="group.stage"
        class="board-column"
        :aria-label="group.title"
      >
        <h2>
          {{ group.title }} <small>{{ group.items.length }} 条已加载</small>
        </h2>
        <article v-for="app in group.items" :key="app.id" class="flat-row">
          <h3>
            <RouterLink :to="'/applications/' + app.id">{{
              app.company
            }}</RouterLink>
          </h3>
          <p>{{ app.title }}</p>
          <p class="muted">{{ app.company_status_raw || "企业状态未记录" }}</p>
          <RouterLink :to="'/applications/' + app.id"
            >查看与记录进度 →</RouterLink
          >
        </article>
        <p v-if="!group.items.length" class="muted">
          当前已加载记录中暂无此阶段申请。
        </p>
      </section>
    </div></template
  >
  <div class="toolbar">
    <el-button
      :disabled="!route.query.cursor"
      @click="router.replace({ query: { ...route.query, cursor: undefined } })"
      >第一页</el-button
    ><el-button
      :disabled="!apps.data.value?.has_more"
      @click="
        router.replace({
          query: {
            ...route.query,
            cursor: apps.data.value?.next_cursor ?? undefined,
          },
        })
      "
      >下一页</el-button
    >
  </div>
  <DraftDrawer
    v-model="show"
    title="补录申请"
    :dirty="creation.dirty.value"
    :busy="busy"
  >
    <el-alert v-if="error" :title="error" type="error" /><el-form
      label-position="top"
      ><el-form-item label="岗位"
        ><el-input v-model="draft.title" aria-label="申请岗位" /></el-form-item
      ><el-form-item label="公司"
        ><el-input
          v-model="draft.company"
          aria-label="申请公司" /></el-form-item
      ><el-form-item label="岗位链接（可空）"
        ><el-input v-model="draft.job_url" /></el-form-item
      ><el-form-item label="投递入口（可空）"
        ><el-input v-model="draft.apply_url" /></el-form-item
      ><el-form-item label="进度入口（可空）"
        ><el-input v-model="draft.progress_url" /></el-form-item
      ><el-form-item label="导航说明"
        ><el-input v-model="draft.navigation_hint" /></el-form-item
      ><el-button
        type="primary"
        :loading="busy"
        :disabled="!draft.title || !draft.company"
        @click="create"
        >创建申请档案</el-button
      ></el-form
    ></DraftDrawer
  >
</template>
