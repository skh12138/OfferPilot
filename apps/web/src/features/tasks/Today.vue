<script setup lang="ts">
import { computed, ref } from "vue";
import DraftDrawer from "../../components/DraftDrawer.vue";
import { useDraft } from "../../app/ui";
import { formatDate } from "../../utils/dates";
import { useListPosition } from "../../app/navigation";

import { useQuery } from "@tanstack/vue-query";
import { client, unwrap } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
import TaskCard from "./TaskCard.vue";
const session = useSession(),
  { busy, error, act } = useAction();
const today = useQuery({
  queryKey: ["today", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/dashboard/today")),
});
const creation = useDraft("task-create", () => ({
  title: "",
  due_date: "",
  deliverable: "",
  acceptance: "",
}));
const draft = creation.draft,
  show = ref(false);
const groups = computed(() => {
  const data = today.data.value;
  const overdue = data?.overdue ?? [];
  const used = new Set(overdue.map((t) => t.id));
  const current = (data?.tasks ?? []).filter((t) => !used.has(t.id));
  current.forEach((t) => used.add(t.id));
  const upcoming = (data?.next_seven_days ?? []).filter((t) => !used.has(t.id));
  return [
    { title: "今日与未排期事项", items: current },
    { title: "已逾期", items: overdue },
    { title: "未来七天", items: upcoming },
  ];
});
useListPosition(computed(() => !today.isPending.value));
async function create() {
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/tasks", {
        body: {
          ...draft.value,
          due_date: draft.value.due_date || null,
          kind: "other",
        },
      }),
    );
    draft.value.title = "";
    creation.saved();
    show.value = false;
    await today.refetch();
  });
}
</script>
<template>
  <h1>今天，推进一小步</h1>
  <p class="subtitle">
    关注到期事项、面试安排与待确认资料。站内提醒按 Asia/Shanghai 显示。
  </p>
  <el-alert
    v-if="today.error.value || (error && !show)"
    :title="error || '读取失败，可刷新重试'"
    type="error"
  /><el-button v-if="today.error.value" @click="today.refetch()"
    >重新加载今日事项</el-button
  ><el-skeleton v-if="today.isPending.value" animated />
  <div class="toolbar">
    <el-button type="primary" @click="show = true">新建待办</el-button>
  </div>
  <div class="metrics">
    <div class="metric">
      今日待办<strong>{{ today.data.value?.tasks.length ?? "—" }}</strong>
    </div>
    <div class="metric">
      未来七天<strong>{{
        today.data.value?.next_seven_days.length ?? "—"
      }}</strong>
    </div>
    <div class="metric">
      已逾期<strong>{{ today.data.value?.overdue.length ?? "—" }}</strong>
    </div>
    <div class="metric">
      待确认事实<strong>{{
        today.data.value?.pending_confirmation ?? "—"
      }}</strong>
    </div>
  </div>
  <DraftDrawer
    v-model="show"
    title="新建待办"
    :dirty="creation.dirty.value"
    :busy="busy"
  >
    <el-alert v-if="error" :title="error" type="error" />
    <el-form label-position="top" @submit.prevent="create"
      ><div class="grid">
        <el-form-item label="下一步"
          ><el-input
            v-model="draft.title"
            aria-label="待办标题" /></el-form-item
        ><el-form-item label="截止日期（可空）"
          ><el-date-picker
            v-model="draft.due_date"
            value-format="YYYY-MM-DD" /></el-form-item
        ><el-form-item label="交付物"
          ><el-input v-model="draft.deliverable" /></el-form-item
        ><el-form-item label="完成标准"
          ><el-input v-model="draft.acceptance"
        /></el-form-item>
      </div>
      <el-button native-type="submit" :loading="busy" :disabled="!draft.title"
        >保存待办</el-button
      ></el-form
    >
  </DraftDrawer>
  <section v-if="today.data.value" class="panel">
    <h2>未来七天日程与回复期限</h2>
    <p v-for="round in today.data.value.rounds" :key="round.id">
      <RouterLink :to="'/applications/' + round.application_id"
        >{{ round.name }} · {{ formatDate(round.planned_at) }}</RouterLink
      >
    </p>
    <p v-for="offer in today.data.value.offer_deadlines" :key="offer.id">
      <RouterLink to="/reviews"
        >Offer 回复期限 · {{ formatDate(offer.reply_deadline) }} ·
        请本人核实和决定</RouterLink
      >
    </p>
    <p v-for="review in today.data.value.review_due" :key="review.id">
      <RouterLink to="/study"
        >复习 {{ review.topic }} ·
        {{ formatDate(review.next_date) }}</RouterLink
      >
    </p>
  </section>
  <section v-if="today.data.value">
    <section v-for="group in groups" :key="group.title" class="task-group">
      <h2>
        {{ group.title }} <small class="muted">{{ group.items.length }}</small>
      </h2>
      <p v-if="!group.items.length" class="muted">此分组暂无待办。</p>
      <TaskCard
        v-for="task in group.items"
        :key="task.id"
        :task="task"
        @saved="today.refetch()"
      />
    </section>
  </section>
</template>
