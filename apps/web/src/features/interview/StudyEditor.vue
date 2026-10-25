<script setup lang="ts">
import DraftDrawer from "../../components/DraftDrawer.vue";
import { useDraft } from "../../app/ui";
import { clone } from "../../api/clone";
import { computed, ref } from "vue";
import { client, unwrap } from "../../api/client";
import { useAction } from "../../app/action";
import type { components } from "../../api/schema";
const props = defineProps<{ study: components["schemas"]["StudyDTO"] }>(),
  emit = defineEmits<{ saved: [] }>(),
  { busy, error, act } = useAction(),
  show = ref(false),
  form = useDraft<{
    payload?: components["schemas"]["StudyPayload"];
    revision?: number;
  }>(
    () => `study-editor:${props.study.id}`,
    () => ({}),
  );
const payload = computed({
  get: () => form.draft.value.payload,
  set: (value) => {
    form.draft.value.payload = value;
  },
});
async function edit() {
  const v = props.study.current;
  if (!v) return;
  if (form.dirty.value && payload.value) {
    show.value = true;
    return;
  }
  await act(async () => {
    const revision = props.study.revision;
    const questions: components["schemas"]["QuestionInput"][] = [];
    for (let offset = 0; offset < v.questions.length; offset += 3) {
      questions.push(
        ...(await Promise.all(
          v.questions.slice(offset, offset + 3).map(async (q) => {
            const { id, ...body } = q;
            const guidance = unwrap(
              await client.GET("/api/v1/questions/{question_id}/guidance", {
                params: { path: { question_id: id } },
              }),
            );
            return { ...body, ...guidance };
          }),
        )),
      );
    }
    if (props.study.current?.id !== v.id) {
      error.value = "题单版本已变化，请重新打开编辑。";
      return;
    }
    payload.value = {
      topics: clone(v.topics),
      limitations: clone(v.limitations),
      questions,
    };
    form.draft.value.revision = revision;
    form.saved();
    show.value = true;
  });
}
async function save() {
  const data = payload.value,
    current = props.study.current;
  if (!data || !current) return;
  for (let i = 0; i < data.questions.length; i++) {
    const q = data.questions[i],
      old = current.questions[i];
    if (
      q &&
      old &&
      q.prompt !== old.prompt &&
      q.source_kind === "experience_reported"
    ) {
      q.source_kind = "generated_for_target";
      q.inspired_by = q.source_refs;
      q.source_refs = [];
    }
  }
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/study-packages/{package_id}/versions", {
        params: { path: { package_id: props.study.id } },
        body: {
          expected_revision: form.draft.value.revision ?? props.study.revision,
          data,
          reason: "本人修改题单，新版本需重新采用",
        },
      }),
    );
    form.saved();
    show.value = false;
    emit("saved");
  });
}
</script>
<template>
  <el-button
    :disabled="!study.current || study.current.deleted"
    :loading="busy"
    @click="edit"
    >编辑题单为新版本</el-button
  ><el-alert v-if="error" :title="error" type="error" /><DraftDrawer
    :dirty="form.dirty.value"
    :busy="busy"
    v-model="show"
    title="编辑题面，保留来源和事实边界"
    ><el-form v-if="payload" label-position="top"
      ><el-form-item
        v-for="(question, index) in payload.questions"
        :key="index"
        :label="`${index + 1} · ${question.topic}`"
        ><el-input v-model="question.prompt" type="textarea"
      /></el-form-item>
      <p class="muted">改编面经题会改标为目标生成；保存后旧审批不再适用。</p>
      <el-button type="primary" :loading="busy" @click="save"
        >保存新的题单版本</el-button
      ></el-form
    ></DraftDrawer
  >
</template>
