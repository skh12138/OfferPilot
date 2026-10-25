<script setup lang="ts">
import ReportForm from "../../components/ReportForm.vue";
import { useDraft } from "../../app/ui";
import { formatDate } from "../../utils/dates";
import { difficultyLabel } from "../../utils/labels";
import { computed, ref, watch } from "vue";
import { useQuery } from "@tanstack/vue-query";
import type { components } from "../../api/schema";
import { client, unwrap, key } from "../../api/client";
import { useAction } from "../../app/action";
import { useSession } from "../../app/session";
import RunStatus from "../../components/RunStatus.vue";
const props = defineProps<{
    draftScope?: string;
    question: components["schemas"]["QuestionDTO"];
    sources: components["schemas"]["SourceDTO"][];
  }>(),
  { busy, error, act } = useAction(),
  session = useSession();
const emit = defineEmits<{
  historyLoaded: [questionId: string, answered: boolean];
}>();
const answerDraft = useDraft(
  () => `question:${props.draftScope ?? ""}:${props.question.id}`,
  () => ({ text: "" }),
);
const text = computed({
    get: () => answerDraft.draft.value.text,
    set: (value) => {
      answerDraft.draft.value.text = value;
    },
  }),
  composing = ref(false),
  showGuidance = ref(false),
  attemptId = ref(""),
  runId = ref("");
const attempts = useQuery({
  queryKey: computed(() => ["attempts", session.user?.id, props.question.id]),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/questions/{question_id}/attempts", {
        params: { path: { question_id: props.question.id } },
      }),
    ),
});
watch(
  () => attempts.data.value?.items,
  (items) => {
    if (items) emit("historyLoaded", props.question.id, items.length > 0);
    const latest = items?.[0];
    if (latest && !attemptId.value) {
      attemptId.value = latest.id;
      runId.value = latest.feedback_run_id ?? "";
    }
  },
  { immediate: true },
);
const feedbackRun = useQuery({
  queryKey: computed(() => ["run", session.user?.id, runId.value]),
  enabled: computed(() => !!runId.value),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/runs/{run_id}", {
        params: { path: { run_id: runId.value } },
      }),
    ),
  refetchInterval: false,
});
const feedbackPending = computed(
  () =>
    !!runId.value &&
    !["succeeded", "partial", "failed", "cancelled"].includes(
      feedbackRun.data.value?.status ?? "",
    ),
);
const feedback = useQuery({
  queryKey: computed(() => ["feedback", session.user?.id, attemptId.value]),
  enabled: computed(() => !!attemptId.value),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/attempts/{attempt_id}/feedback", {
        params: { path: { attempt_id: attemptId.value } },
      }),
    ),
});
const guidance = useQuery({
  queryKey: computed(() => ["guidance", session.user?.id, props.question.id]),
  enabled: showGuidance,
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/questions/{question_id}/guidance", {
        params: { path: { question_id: props.question.id } },
      }),
    ),
});
async function answer() {
  if (composing.value) return;
  await act(async () => {
    const attempt = unwrap(
      await client.POST("/api/v1/questions/{question_id}/attempts", {
        params: { path: { question_id: props.question.id } },
        headers: key(),
        body: { answer: text.value },
      }),
    );
    answerDraft.saved();
    attemptId.value = attempt.id;
    runId.value = attempt.feedback_run_id ?? "";
    if (attempt.feedback_error_code)
      error.value = `回答已保存；反馈未启动：${attempt.feedback_error_code}`;
    await attempts.refetch();
  });
}
async function retry() {
  await act(async () => {
    const run = unwrap(
      await client.POST("/api/v1/attempts/{attempt_id}/feedback-retry", {
        params: { path: { attempt_id: attemptId.value } },
        headers: key(),
      }),
    );
    runId.value = run.id;
  });
}
const sourceLabels: Record<string, string> = {
  generated_for_target: "基于目标岗位生成",
  experience_reported: "历史分享提及 · 作者自述",
  general_practice: "通用知识练习",
};
</script>
<template>
  <article class="panel question-practice">
    <div class="tags">
      <el-tag>{{ question.topic }}</el-tag
      ><el-tag type="info">{{ sourceLabels[question.source_kind] }}</el-tag
      ><span>难度：{{ difficultyLabel(question.difficulty) }}</span>
    </div>
    <h2>{{ question.prompt }}</h2>
    <p>推荐依据：{{ question.recommendation_reason }}</p>
    <p v-for="ref in question.source_refs" :key="ref.source_id">
      <a
        :href="sources.find((s) => s.id === ref.source_id)?.url"
        target="_blank"
        rel="noopener noreferrer"
        >查看面经来源 ↗</a
      >
      · {{ ref.quote }}
    </p>
    <p v-if="question.quality_flags.length" class="muted">
      {{ question.quality_flags.join("；") }}
    </p>
    <el-form label-position="top" @submit.prevent="answer"
      ><el-form-item label="我的回答"
        ><el-input
          v-model="text"
          type="textarea"
          :rows="5"
          aria-label="我的回答"
          @compositionstart="composing = true"
          @compositionend="composing = false" /></el-form-item
      ><el-button
        type="primary"
        native-type="submit"
        :loading="busy"
        :disabled="!text || composing"
        >保存回答并请求反馈</el-button
      ><el-button @click="showGuidance = !showGuidance">{{
        showGuidance ? "收起提示与要点" : "查看提示与答案要点"
      }}</el-button></el-form
    ><el-alert v-if="error" :title="error" type="error" />
    <div v-if="showGuidance && guidance.data.value" class="evidence">
      <p>{{ guidance.data.value.hints.join("；") }}</p>
      <p>{{ guidance.data.value.answer_guidance }}</p>
      <p>评价要点：{{ guidance.data.value.rubric.join("；") }}</p>
      <p class="muted">查看要点不会自动标记掌握。</p>
    </div>
    <p class="draft-note muted">
      未提交回答会在当前登录会话内按题目保留，刷新会丢失；保存成功后以回答历史为准。
    </p>
    <RunStatus v-if="runId" :id="runId" @complete="feedback.refetch()" />
    <section v-if="attemptId">
      <h3>反馈与回答历史</h3>
      <p class="muted">
        所选回答版本：{{
          formatDate(
            attempts.data.value?.items.find((a) => a.id === attemptId)
              ?.created_at,
          )
        }}；切换历史不会覆盖当前草稿。
      </p>
      <el-alert
        v-if="
          !feedbackPending &&
          !feedback.data.value?.items.length &&
          !feedback.isPending.value
        "
        title="回答已保存，反馈未完成，可重试反馈。"
        type="warning"
      />
      <el-button
        v-if="
          !feedback.isPending.value &&
          !feedbackPending &&
          !feedback.data.value?.items.length
        "
        @click="retry"
        >重试反馈（回答已保存）</el-button
      >
      <div
        v-for="item in feedback.data.value?.items"
        :key="item.id"
        class="evidence"
      >
        <p>反馈版本 {{ item.version }} · {{ item.model }}</p>
        <p>优点：{{ item.data.strengths.join("；") }}</p>
        <p>可改进：{{ item.data.issues.join("；") }}</p>
        <p>修改提纲：{{ item.data.suggested_revision_outline.join(" → ") }}</p>
        <p>{{ item.data.follow_up_question }}</p>
        <p class="muted">{{ item.data.uncertainties.join("；") }}</p>
      </div>
      <p
        v-for="attempt in attempts.data.value?.items"
        :key="attempt.id"
        class="evidence"
      >
        {{ formatDate(attempt.created_at) }}<br />{{ attempt.answer }}
        <el-button
          link
          @click="
            attemptId = attempt.id;
            runId = attempt.feedback_run_id ?? '';
          "
          >查看该次反馈</el-button
        >
      </p>
    </section>
    <ReportForm kind="question" :id="question.id" />
  </article>
</template>
