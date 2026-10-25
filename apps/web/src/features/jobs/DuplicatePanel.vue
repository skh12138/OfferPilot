<script setup lang="ts">
import { ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { client, unwrap } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
import type { components } from "../../api/schema";
const emit = defineEmits<{ saved: [] }>(),
  session = useSession(),
  { busy, error, act } = useAction(),
  reason = ref("");
const duplicates = useQuery({
  queryKey: ["duplicates", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/duplicate-reviews")),
});
const merges = useQuery({
  queryKey: ["merges", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/job-merges")),
});
async function decide(
  row: components["schemas"]["DuplicateDTO"],
  decision: "merge" | "keep_separate",
) {
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/duplicate-reviews/{review_id}/decision", {
        params: { path: { review_id: row.id } },
        body: {
          expected_revision: row.revision,
          decision,
          reason: reason.value,
        },
      }),
    );
    await duplicates.refetch();
    await merges.refetch();
    emit("saved");
  });
}
async function undo(id: string) {
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/job-merges/{merge_id}/undo", {
        params: { path: { merge_id: id } },
      }),
    );
    await merges.refetch();
    emit("saved");
  });
}
</script>
<template>
  <el-collapse
    v-if="
      duplicates.data.value?.items.length || merges.data.value?.items.length
    "
    class="panel"
    ><el-collapse-item title="疑似重复与合并历史"
      ><el-alert v-if="error" :title="error" type="error" /><label
        for="duplicate-reason"
        >决定依据（核对来源后填写）</label
      ><el-input
        id="duplicate-reason"
        v-model="reason"
        placeholder="核对来源后的决定依据"
        aria-label="去重决定依据"
      />
      <article
        v-for="pair in duplicates.data.value?.items"
        :key="pair.id"
        class="fact"
      >
        <p>{{ pair.reason }}</p>
        <RouterLink :to="'/jobs/' + pair.left_id">查看岗位 A</RouterLink> ·
        <RouterLink :to="'/jobs/' + pair.right_id">查看岗位 B</RouterLink>
        <div v-if="!pair.decision" class="toolbar">
          <el-button
            :loading="busy"
            :disabled="!reason"
            @click="decide(pair, 'merge')"
            >本人确认同一岗位，合并展示</el-button
          ><el-button
            :disabled="!reason || busy"
            @click="decide(pair, 'keep_separate')"
            >保留为不同岗位</el-button
          >
        </div>
        <p v-else>
          {{ pair.decision === "merge" ? "已合并展示" : "已确认不重复" }}
        </p>
      </article>
      <p v-for="merge in merges.data.value?.items" :key="merge.id">
        {{ merge.undone ? "合并已撤销" : "已建立合并关联" }}
        <el-button v-if="!merge.undone" link @click="undo(merge.id)"
          >撤销合并，保留全部历史</el-button
        >
      </p></el-collapse-item
    ></el-collapse
  >
</template>
