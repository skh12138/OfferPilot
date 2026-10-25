<script setup lang="ts">
import { formatDate } from "../../utils/dates";
import { label } from "../../utils/labels";
import type { components } from "../../api/schema";
import { client, unwrap } from "../../api/client";
import { useAction } from "../../app/action";
const props = defineProps<{ task: components["schemas"]["TaskDTO"] }>(),
  emit = defineEmits<{ saved: [] }>(),
  { error, busy, act } = useAction();
async function update(status: components["schemas"]["TaskPatch"]["status"]) {
  const t = props.task;
  await act(async () => {
    unwrap(
      await client.PATCH("/api/v1/tasks/{task_id}", {
        params: { path: { task_id: t.id } },
        body: {
          expected_revision: t.revision,
          title: t.title,
          kind: t.kind,
          application_id: t.application_id,
          round_id: t.round_id,
          status,
          due_at: t.due_at,
          due_date: t.due_date,
          deliverable: t.deliverable,
          acceptance: t.acceptance,
        },
      }),
    );
    emit("saved");
  });
}
</script>
<template>
  <article class="flat-row task-row">
    <div class="row-top">
      <h3>{{ task.title }}</h3>
      <div class="tags">
        <el-tag disable-transitions>{{ label(task.status ?? "待核实") }}</el-tag
        ><el-tag v-if="task.overdue" type="danger" disable-transitions
          >已逾期</el-tag
        >
      </div>
    </div>
    <p>
      {{
        task.due_at
          ? formatDate(task.due_at)
          : task.due_date
            ? formatDate(task.due_date)
            : "无截止日期"
      }}
    </p>
    <p v-if="task.deliverable">交付：{{ task.deliverable }}</p>
    <p v-if="task.acceptance">验收：{{ task.acceptance }}</p>
    <el-alert v-if="error" :title="error" type="error" />
    <div class="toolbar">
      <el-button :loading="busy" @click="update('done')">标记完成</el-button
      ><el-button @click="update('waiting_external')">等待外部</el-button
      ><el-button link @click="update('cancelled')">取消</el-button
      ><RouterLink
        v-if="task.application_id"
        :to="'/applications/' + task.application_id"
        >查看申请 →</RouterLink
      >
    </div>
  </article>
</template>
