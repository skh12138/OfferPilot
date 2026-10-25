<script setup lang="ts">
import { computed } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { client, unwrap } from "../api/client";
import { useSession } from "../app/session";
import { label } from "../utils/labels";
import type { components } from "../api/schema";
const session = useSession();
const runs = useQuery({
  queryKey: computed(() => ["runs", session.user?.id]),
  enabled: computed(() => !!session.user),
  queryFn: async () => unwrap(await client.GET("/api/v1/runs")),
  refetchInterval: 5000,
});
const active = computed(
  () =>
    runs.data.value?.items
      .filter((r) =>
        ["running", "queued", "failed", "partial"].includes(r.status),
      )
      .slice(0, 8) ?? [],
);
function path(run: components["schemas"]["RunDTO"]) {
  if (run.kind === "search_organize")
    return `/discover?run=${String(run.result.source_search_run_id ?? "")}&organize=${run.id}`;
  const base = run.application_id
    ? `/applications/${run.application_id}`
    : run.kind === "resume_parse"
      ? "/profile"
      : run.kind === "search" || run.kind === "search_parse"
        ? "/discover"
        : run.kind === "study" || run.kind === "feedback"
          ? "/study"
          : "/jobs";
  return base + "?run=" + run.id;
}
</script>
<template>
  <el-collapse v-if="active.length" class="pending-runs"
    ><el-collapse-item
      :title="`近期处理中与未完成事项（显示 ${active.length} 项）`"
      ><p v-for="run in active" :key="run.id">
        <RouterLink :to="path(run)"
          >{{ label(run.kind) }} · {{ label(run.status) }} →</RouterLink
        >
      </p></el-collapse-item
    ></el-collapse
  >
</template>
