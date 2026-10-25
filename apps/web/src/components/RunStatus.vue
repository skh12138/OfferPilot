<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { label } from "../utils/labels";
import { client, unwrap, key } from "../api/client";
import { useSession } from "../app/session";
import { useAction } from "../app/action";
const props = defineProps<{ id: string; compact?: boolean }>(),
  emit = defineEmits<{ complete: [] }>();
const session = useSession(),
  route = useRoute(),
  router = useRouter(),
  cache = useQueryClient(),
  { busy, act, error } = useAction();
const terminal = ["succeeded", "partial", "failed", "cancelled"];
const run = useQuery({
  queryKey: computed(() => ["run", session.user?.id, props.id]),
  enabled: computed(() => !!session.user && !!props.id),
  queryFn: async ({ signal }) =>
    unwrap(
      await client.GET("/api/v1/runs/{run_id}", {
        params: { path: { run_id: props.id } },
        signal,
      }),
    ),
  refetchInterval: (q) =>
    terminal.includes(q.state.data?.status ?? "") ? false : 2000,
});
const completed = new Set<string>();
watch(
  () => run.data.value,
  (record) => {
    if (
      !record ||
      !terminal.includes(record.status) ||
      completed.has(record.id)
    )
      return;
    completed.add(record.id);
    const groups: Record<string, string[]> = {
      search: ["candidates", "specs", "jobs"],
      search_organize: ["candidates"],
      resume_parse: ["profile", "resumes"],
      job_import: ["jobs", "duplicates", "merges"],
      study: ["study", "review-items", "today"],
      feedback: ["feedback", "attempts"],
      material_prepare: ["bundles", "tasks", "today"],
    };
    const prefixes = ["runs", ...(groups[record.kind] ?? [])];
    void cache.invalidateQueries({
      predicate: (q) => prefixes.includes(String(q.queryKey[0])),
    });
    emit("complete");
  },
  { immediate: true },
);
const counts = computed<Record<string, unknown>>(() => {
  const value = run.data.value?.result.counts;
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
});
const details: Record<string, string> = {
  unique_urls: "来源",
  organized_positions: "职位记录",
  unique_opportunities: "去重机会",
  new_jobs: "新岗位",
  updated_jobs: "更新岗位",
  partial_candidates: "待核实来源",
  organization_errors: "整理失败步骤",
};
const errorMessage = computed(
  () =>
    ({
      budget_exhausted: "达到本次处理预算，已取得的结果已保留。",
      provider_not_configured: "服务尚未配置，请检查服务端配置。",
      model_semantic_invalid:
        "生成内容未通过结构或证据校验，可修正输入后重试。",
      content_unavailable: "部分来源暂时无法读取，已保留可用信息。",
    })[run.data.value?.error_code ?? ""],
);
async function cancel() {
  await act(async () =>
    unwrap(
      await client.POST("/api/v1/runs/{run_id}/cancel", {
        params: { path: { run_id: props.id } },
      }),
    ),
  );
  await run.refetch();
}
async function retry() {
  await act(async () => {
    const r = unwrap(
      await client.POST("/api/v1/runs/{run_id}/retry", {
        params: { path: { run_id: props.id } },
        headers: key(),
      }),
    );
    await cache.invalidateQueries({ queryKey: ["runs", session.user?.id] });
    await router.replace({
      query: {
        ...route.query,
        ...(r.kind === "search_organize" ? { organize: r.id } : { run: r.id }),
      },
    });
  });
}
</script>
<template>
  <section class="run-status" aria-label="处理进度">
    <div class="row-top">
      <div class="tags">
        <strong>处理进度</strong
        ><span v-if="run.data.value" role="status"
          ><el-tag
            :type="
              run.data.value.status === 'failed'
                ? 'danger'
                : run.data.value.status === 'partial'
                  ? 'warning'
                  : 'info'
            "
            >{{ label(run.data.value.status) }}</el-tag
          >
          {{ label(run.data.value.kind) }}</span
        ><span v-else>正在读取</span>
      </div>
      <div class="toolbar">
        <el-button
          v-if="run.data.value && !terminal.includes(run.data.value.status)"
          :loading="busy"
          @click="cancel"
          >取消</el-button
        ><el-button
          v-if="
            run.data.value &&
            ['partial', 'failed', 'cancelled'].includes(run.data.value.status)
          "
          :loading="busy"
          @click="retry"
          >重试</el-button
        >
      </div>
    </div>
    <el-alert
      v-if="error || run.error.value"
      :title="error || '无法读取进度，请重试'"
      type="error"
    /><el-button v-if="run.error.value" @click="run.refetch()"
      >重新加载进度</el-button
    >
    <template v-if="run.data.value"
      ><p v-if="run.data.value.status === 'queued'" class="muted">
        已提交，等待后台处理。离开页面后仍会继续。
      </p>
      <p v-else-if="run.data.value.status === 'running'" class="muted">
        正在处理，已保存的结果会陆续出现。
      </p>
      <p v-else-if="run.data.value.status === 'partial'" class="muted">
        部分完成，可用结果已保留；部分来源或步骤未完成，可查看原因后重试。
      </p>
      <p v-else-if="run.data.value.status === 'cancelled'" class="muted">
        已取消后续处理，已保存的结果仍可查看。
      </p>
      <p v-if="run.data.value.error_code" role="alert">
        {{
          errorMessage ||
          "本次处理未完全完成，请检查输入、来源或服务状态后重试。"
        }}
        <small>（{{ run.data.value.error_code }}）</small>
      </p>
      <div
        v-if="run.data.value.status === 'partial' || !compact"
        class="row-meta"
      >
        <template v-for="(name, field) in details" :key="field"
          ><span v-if="typeof counts[field] === 'number'"
            >{{ name }} {{ counts[field] }}</span
          ></template
        >
      </div>
      <RouterLink
        v-if="run.data.value.result.study_package_id"
        :to="`/study/${run.data.value.result.study_package_id}`"
        >打开训练包 →</RouterLink
      ><RouterLink v-if="run.data.value.result.job_ids" to="/jobs"
        >查看岗位库 →</RouterLink
      >
    </template>
  </section>
</template>
