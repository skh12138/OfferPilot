<script setup lang="ts">
import { useDraft } from "../../app/ui";
import { computed } from "vue";
import { clone } from "../../api/clone";
import { ref, watch } from "vue";
import type { components } from "../../api/schema";
import { client, key, unwrap } from "../../api/client";
import { useAction } from "../../app/action";
const props = defineProps<{ bundle: components["schemas"]["BundleDTO"] }>(),
  emit = defineEmits<{ saved: [] }>(),
  { busy, error, act } = useAction();
const editing = ref(false),
  form = useDraft<{
    payload?: components["schemas"]["BundlePayload"];
    revision?: number;
  }>(
    () => `bundle:${props.bundle.id}`,
    () => ({}),
  );
const draft = computed({
  get: () => form.draft.value.payload,
  set: (value) => {
    form.draft.value.payload = value;
  },
});
watch(
  () => props.bundle.current,
  (value) => {
    if (!form.dirty.value) {
      draft.value = value?.data ? clone(value.data) : undefined;
      form.draft.value.revision = props.bundle.revision;
      form.saved();
    }
  },
  { immediate: true },
);
async function save() {
  const payload = draft.value;
  if (!payload) return;
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/preparation-bundles/{bundle_id}/versions", {
        params: { path: { bundle_id: props.bundle.id } },
        body: {
          data: payload,
          expected_revision: form.draft.value.revision ?? props.bundle.revision,
          reason: "本人编辑草稿",
        },
      }),
    );
    form.saved();
    editing.value = false;
    emit("saved");
  });
}
async function approve() {
  const v = props.bundle.current;
  if (!v) return;
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/preparation-bundles/{bundle_id}/approve", {
        params: { path: { bundle_id: props.bundle.id } },
        headers: key(),
        body: {
          expected_revision: props.bundle.revision,
          version_id: v.id,
          payload_hash: v.payload_hash,
          basis_revision: v.basis_revision,
          scope: "tasks,materials",
        },
      }),
    );
    emit("saved");
  });
}
</script>
<template>
  <section class="panel">
    <h2>材料草稿 · 准备基准 {{ bundle.current?.basis_revision }}</h2>
    <el-alert v-if="error" type="error" :title="error" />
    <p v-if="bundle.current?.deleted">资料已删除</p>
    <template v-else-if="draft"
      ><p class="muted">
        请逐条审核事实与任务；批准只保存站内内容，不代表投递或对外发送。
      </p>
      <article
        v-for="claim in draft.claims"
        :key="claim.fact_ids.join(',')"
        class="fact"
      >
        <el-input v-if="editing" v-model="claim.text" type="textarea" />
        <p v-else>{{ claim.text }}</p>
        <blockquote class="evidence">{{ claim.quotes.join(" / ") }}</blockquote>
      </article>
      <h3>准备任务</h3>
      <article v-for="task in draft.tasks" :key="task.title">
        <h3>{{ task.title }}</h3>
        <p>{{ task.reason }}</p>
        <p>交付：{{ task.deliverable }} · 验收：{{ task.acceptance }}</p>
      </article>
      <h3>自我介绍提纲</h3>
      <el-input v-if="editing" v-model="draft.introduction" type="textarea" />
      <p v-else>{{ draft.introduction }}</p>
      <h3>联系草稿</h3>
      <el-input v-if="editing" v-model="draft.contact_draft" type="textarea" />
      <p v-else>{{ draft.contact_draft }}</p>
      <p>待核实：{{ draft.gaps.join("；") }}</p>
      <div class="toolbar">
        <el-button v-if="!editing" @click="editing = true">编辑新版本</el-button
        ><el-button v-else :loading="busy" @click="save"
          >保存新版本并重新审核</el-button
        ><el-button
          type="primary"
          :loading="busy"
          :disabled="editing"
          @click="approve"
          >审核并保存任务与材料</el-button
        >
      </div></template
    >
  </section>
</template>
