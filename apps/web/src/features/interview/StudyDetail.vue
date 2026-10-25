<script setup lang="ts">
import { useWide } from "../../app/navigation";
import StudyEditor from "./StudyEditor.vue";
import { computed, watch, reactive } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQuery } from "@tanstack/vue-query";
import { client, unwrap, key } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
import QuestionPractice from "./QuestionPractice.vue";
const route = useRoute(),
  router = useRouter(),
  id = computed(() => String(route.params.id)),
  session = useSession(),
  { busy, error, act } = useAction();
const study = useQuery({
  queryKey: computed(() => ["study", session.user?.id, id.value]),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/study-packages/{package_id}", {
        params: { path: { package_id: id.value } },
      }),
    ),
});
const sources = useQuery({
  queryKey: ["interview-sources", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/interview-sources")),
});
async function adopt() {
  const pack = study.data.value,
    version = pack?.current;
  if (!pack || !version) return;
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/study-packages/{package_id}/adopt", {
        params: { path: { package_id: id.value } },
        headers: key(),
        body: {
          expected_revision: pack.revision,
          version_id: version.id,
          payload_hash: version.payload_hash,
          basis_revision: version.basis_revision,
        },
      }),
    );
    await study.refetch();
  });
}
const wide = useWide();
const answered = reactive<Record<string, boolean>>({});
const questions = computed(() => study.data.value?.current?.questions ?? []);
const current = computed(
  () =>
    questions.value.find((q) => q.id === route.query.question) ??
    (!route.query.question ? questions.value[0] : undefined),
);
const index = computed(() =>
  questions.value.findIndex((q) => q.id === current.value?.id),
);
function choose(id: string) {
  void router.replace({ query: { ...route.query, question: id } });
}
watch(
  () => study.data.value?.current?.id,
  () => {
    if (!route.query.question && questions.value[0])
      choose(questions.value[0].id);
  },
);
</script>
<template>
  <RouterLink to="/study">← 面试准备</RouterLink>
  <h1 style="margin-top: 20px">岗位训练包</h1>
  <el-alert
    v-if="error || study.error.value"
    :title="error || '读取失败'"
    type="error"
  /><el-button v-if="study.error.value" @click="study.refetch()"
    >重新加载训练包</el-button
  ><el-skeleton v-if="study.isPending.value" animated /><template
    v-if="study.data.value?.current"
    ><el-collapse
      ><el-collapse-item title="能力地图、来源限制与题单版本"
        ><section class="panel">
          <h2>能力地图</h2>
          <StudyEditor
            v-if="study.data.value"
            :study="study.data.value"
            @saved="study.refetch()"
          />
          <p
            v-for="topic in study.data.value.current.topics"
            :key="topic.topic"
          >
            <strong>{{ topic.topic }}</strong> · {{ topic.reason }}
          </p>
          <el-alert
            v-for="limit in study.data.value.current.limitations"
            :key="limit"
            :title="limit"
            type="info"
            :closable="false"
          />
          <p class="muted">生成后不会自动创建正式任务；采用后也不代表掌握。</p>
        </section></el-collapse-item
      ></el-collapse
    >
    <el-button
      type="primary"
      :loading="busy"
      :disabled="
        study.data.value.current.adopted || study.data.value.current.deleted
      "
      @click="adopt"
      >{{
        study.data.value.current.adopted
          ? "题单已采用"
          : "采用题单并建立复习任务"
      }}</el-button
    >
    <div class="practice-workspace">
      <nav class="question-directory" aria-label="题目目录">
        <details :open="wide">
          <summary>题目目录</summary>
          <ol>
            <li v-for="(q, n) in questions" :key="q.id">
              <button
                type="button"
                :aria-current="current?.id === q.id ? 'step' : undefined"
                @click="choose(q.id)"
              >
                <span>{{ n + 1 }} · {{ q.topic }}</span
                ><small>{{
                  answered[q.id] === true
                    ? "已有回答"
                    : answered[q.id] === false
                      ? "尚未回答"
                      : "回答状态未加载"
                }}</small>
              </button>
            </li>
          </ol>
        </details>
      </nav>
      <div class="practice-current">
        <template v-if="current"
          ><div class="row-top">
            <span class="muted"
              >第 {{ index + 1 }} / {{ questions.length }} 题</span
            >
            <div class="toolbar">
              <el-button
                :disabled="index <= 0"
                @click="choose(questions[index - 1]!.id)"
                >上一题</el-button
              ><el-button
                :disabled="index >= questions.length - 1"
                @click="choose(questions[index + 1]!.id)"
                >下一题</el-button
              >
            </div>
          </div>
          <QuestionPractice
            :key="current.id"
            :question="current"
            :draft-scope="id + ':' + study.data.value.current.id"
            :sources="sources.data.value?.items ?? []"
            @history-loaded="
              (questionId, hasAnswer) => {
                answered[questionId] = hasAnswer;
              }
            "
        /></template>
        <div v-else class="state-box">
          <h2>题单版本已变化</h2>
          <p>
            原题目不在当前版本中。旧草稿仍按原题目隔离保留，请选择当前题目后再作答。
          </p>
          <el-button v-if="questions[0]" @click="choose(questions[0].id)"
            >载入当前第一题</el-button
          >
        </div>
      </div>
    </div></template
  >
</template>
