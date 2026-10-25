<script setup lang="ts">
import { useDraft } from "../../app/ui";
import { watch } from "vue";
import DraftDrawer from "../../components/DraftDrawer.vue";
import { label } from "../../utils/labels";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQuery } from "@tanstack/vue-query";
import { client, key, unwrap } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
import RunStatus from "../../components/RunStatus.vue";
const session = useSession(),
  route = useRoute(),
  router = useRouter(),
  { busy, error, act } = useAction();
const runId = computed({
    get: () => String(route.query.run ?? ""),
    set: (run) => {
      void router.replace({ query: { ...route.query, run } });
    },
  }),
  jobId = ref(""),
  appId = computed({
    get: () => String(route.query.application ?? ""),
    set: (value) => {
      void router.replace({
        query: {
          ...route.query,
          application: value || undefined,
          round: undefined,
        },
      });
    },
  }),
  count = ref(8),
  showCreate = ref(false);
const roundId = computed({
    get: () => String(route.query.round ?? ""),
    set: (value) => {
      void router.replace({
        query: { ...route.query, round: value || undefined },
      });
    },
  }),
  interviewDate = ref<string | undefined>();
const rounds = useQuery({
  queryKey: computed(() => ["rounds", session.user?.id, appId.value]),
  enabled: computed(() => !!appId.value),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/applications/{app_id}/rounds", {
        params: { path: { app_id: appId.value } },
      }),
    ),
});
const capabilities = useQuery({
  queryKey: ["capabilities"],
  queryFn: async () => unwrap(await client.GET("/api/v1/capabilities")),
});
const packages = useQuery({
  queryKey: ["study", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/study-packages")),
});
const jobs = useQuery({
  queryKey: ["jobs", session.user?.id],
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/jobs", { params: { query: { limit: 100 } } }),
    ),
});
const apps = useQuery({
  queryKey: ["applications", session.user?.id],
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/applications", {
        params: { query: { limit: 100 } },
      }),
    ),
});
const reviews = useQuery({
  queryKey: ["review-items", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/review-items")),
});
const profile = useQuery({
  queryKey: ["profile", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/profiles/current")),
});
const createMemory = useDraft("study-create", () => ({
  job: jobId.value,
  count: count.value,
  date: interviewDate.value,
}));
jobId.value = createMemory.draft.value.job;
count.value = createMemory.draft.value.count;
interviewDate.value = createMemory.draft.value.date;
watch(
  [jobId, count, interviewDate],
  () => {
    createMemory.draft.value = {
      job: jobId.value,
      count: count.value,
      date: interviewDate.value,
    };
  },
  { flush: "sync" },
);
async function generate() {
  await act(async () => {
    const run = unwrap(
      await client.POST("/api/v1/study-package-runs", {
        body: {
          application_id: appId.value || null,
          job_version_id: jobId.value || null,
          profile_version_id: profile.data.value?.current?.id ?? null,
          count: count.value,
          round_id: roundId.value || null,
          interview_date: interviewDate.value,
          include_interview_search: true,
        },
        headers: key(),
      }),
    );
    runId.value = run.id;
    createMemory.saved();
    showCreate.value = false;
  });
}
async function review(
  id: string,
  revision: number,
  mastery: "needs_review" | "practicing" | "confident",
  next_date?: string,
) {
  await act(async () => {
    unwrap(
      await client.PATCH("/api/v1/review-items/{item_id}", {
        params: { path: { item_id: id } },
        body: {
          expected_revision: revision,
          mastery,
          next_date,
          user_correction: "本人调整复习状态或日期",
        },
      }),
    );
    await reviews.refetch();
  });
}
</script>
<template>
  <h1>为下一场面试做准备</h1>
  <p class="subtitle">
    围绕当前 JD 与实际投递资料练习。历史分享、目标生成与通用练习分别标识。
  </p>
  <el-alert v-if="error && !showCreate" :title="error" type="error" />
  <div class="toolbar">
    <el-button type="primary" @click="showCreate = true">创建短题单</el-button>
  </div>
  <DraftDrawer
    v-model="showCreate"
    title="创建短题单"
    :busy="busy"
    :dirty="createMemory.dirty.value"
  >
    <el-alert v-if="error" :title="error" type="error" />
    <el-form label-position="top"
      ><div class="stack">
        <el-form-item label="关联申请（可空，采用申请的准备基准）"
          ><el-select v-model="appId" clearable
            ><el-option
              v-for="app in apps.data.value?.items"
              :key="app.id"
              :value="app.id"
              :label="
                app.company + ' · ' + app.title
              " /></el-select></el-form-item
        ><el-form-item label="或直接选岗位"
          ><el-select
            v-model="jobId"
            clearable
            :disabled="!!appId"
            aria-label="训练目标岗位"
            ><el-option
              v-for="job in jobs.data.value?.items"
              :key="job.id"
              :value="job.current_version_id ?? job.id"
              :label="
                job.current?.data.title ?? '岗位'
              " /></el-select></el-form-item
        ><el-form-item label="准备哪一轮"
          ><el-select v-model="roundId" clearable :disabled="!appId"
            ><el-option
              v-for="round in rounds.data.value?.items"
              :key="round.id"
              :value="round.id"
              :label="round.name" /></el-select></el-form-item
        ><el-form-item label="面试日期（可空）"
          ><el-date-picker
            v-model="interviewDate"
            value-format="YYYY-MM-DD" /></el-form-item
        ><el-form-item label="题量 5–15"
          ><el-input-number v-model="count" :min="5" :max="15"
        /></el-form-item>
      </div>
      <el-button
        type="primary"
        :loading="busy"
        :disabled="
          (!appId && !jobId) || !capabilities.data.value?.model_available
        "
        @click="generate"
        >生成训练包</el-button
      ></el-form
    >
  </DraftDrawer>
  <RunStatus v-if="runId" :id="runId" @complete="packages.refetch()" />
  <el-alert
    v-if="packages.error.value || reviews.error.value"
    title="训练包或复习记录加载失败，请重试"
    type="error"
  /><el-button
    v-if="packages.error.value || reviews.error.value"
    @click="
      packages.refetch();
      reviews.refetch();
    "
    >重新加载</el-button
  >
  <h2>准备包</h2>
  <el-skeleton v-if="packages.isPending.value" animated />
  <div class="stack">
    <article
      v-for="pack in packages.data.value?.items"
      :key="pack.id"
      class="flat-row"
    >
      <h3>
        <RouterLink :to="'/study/' + pack.id"
          >{{ pack.current?.deleted ? "资料已删除" : "岗位训练包" }} ·
          {{ pack.current?.questions.length }} 题 →</RouterLink
        >
      </h3>
      <p>{{ pack.current?.adopted ? "已采用" : "草稿，尚未创建复习任务" }}</p>
      <p v-for="limit in pack.current?.limitations" :key="limit" class="muted">
        {{ limit }}
      </p>
    </article>
  </div>
  <p
    v-if="
      !packages.isPending.value &&
      !packages.error.value &&
      !packages.data.value?.items.length
    "
    class="panel empty"
  >
    还没有训练包。没有面经或完整简历也可以从岗位开始。
  </p>
  <h2 style="margin-top: 24px">薄弱点与复习</h2>
  <div class="stack">
    <article
      v-for="item in reviews.data.value?.items"
      :key="item.id"
      class="flat-row"
    >
      <h3>{{ item.topic }}</h3>
      <p>
        本人：{{
          item.mastery === "needs_review" ? "需复习" : label(item.mastery)
        }}
        · 模型建议：{{ label(item.ai_suggestion ?? "待评估") }}
      </p>
      <p>下次复习：{{ item.next_date }}</p>
      <div class="toolbar">
        <el-button @click="review(item.id, item.revision, 'needs_review')"
          >需复习</el-button
        ><el-button @click="review(item.id, item.revision, 'practicing')"
          >练习中</el-button
        ><el-button @click="review(item.id, item.revision, 'confident')"
          >本人确认掌握</el-button
        >
      </div>
      <el-date-picker
        :model-value="item.next_date"
        value-format="YYYY-MM-DD"
        @update:model-value="
          (value: unknown) =>
            review(item.id, item.revision, 'needs_review', String(value))
        "
      />
    </article>
  </div>
</template>
