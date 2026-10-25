<script setup lang="ts">
import { ref } from "vue";
import { client, unwrap } from "../../api/client";
import { useAction } from "../../app/action";
import type { components } from "../../api/schema";
const props = defineProps<{ jobId: string }>(),
  emit = defineEmits<{ saved: [] }>(),
  { busy, error, act } = useAction(),
  preference =
    ref<components["schemas"]["PreferenceInput"]["preference"]>("interested"),
  reason = ref("");
async function save() {
  await act(async () => {
    unwrap(
      await client.PUT("/api/v1/jobs/{job_id}/preference", {
        params: { path: { job_id: props.jobId } },
        body: { preference: preference.value, reason: reason.value },
      }),
    );
    emit("saved");
  });
}
</script>
<template>
  <section class="panel">
    <h2>个人意向</h2>
    <label>岗位意向与理由（不考虑时理由必填）</label>
    <div class="toolbar">
      <el-select v-model="preference" aria-label="岗位意向" style="width: 180px"
        ><el-option value="priority" label="重点推进" /><el-option
          value="interested"
          label="一般关注" /><el-option value="paused" label="暂缓" /><el-option
          value="excluded"
          label="不考虑" /></el-select
      ><el-input
        v-model="reason"
        aria-label="意向理由"
        placeholder="选择理由（排除时必填）"
      /><el-button :loading="busy" @click="save">保存意向</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" />
    <p class="muted">只影响本人的筛选与排序，不修改岗位信息。</p>
  </section>
</template>
