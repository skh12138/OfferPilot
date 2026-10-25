<script setup lang="ts">
import { useSession } from "../../app/session";
import { computed, reactive, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { client, key, unwrap } from "../../api/client";
import { useAction } from "../../app/action";
import type { components } from "../../api/schema";
const session = useSession();
const allowed = computed(() => !!session.user?.is_admin);
const { busy, error, act } = useAction(),
  editing = ref<components["schemas"]["PolicyDTO"]>();
const overview = useQuery({
  queryKey: ["operations", session.user?.id],
  enabled: allowed,
  queryFn: async () => unwrap(await client.GET("/api/v1/admin/overview")),
});
const policies = useQuery({
  queryKey: ["source-policies", session.user?.id],
  enabled: allowed,
  queryFn: async () =>
    unwrap(await client.GET("/api/v1/admin/source-policies")),
});
const reports = useQuery({
  queryKey: ["reports", session.user?.id],
  enabled: allowed,
  queryFn: async () =>
    unwrap(await client.GET("/api/v1/admin/feedback-reports")),
});
const draft = reactive<components["schemas"]["PolicyInput"]>({
  domain: "",
  purpose: "jobs",
  mode: "metadata_only",
  store_text: false,
  store_excerpt: true,
  official_evidence: null,
  usage_basis: "",
});
async function save() {
  await act(async () => {
    if (editing.value) {
      unwrap(
        await client.PATCH("/api/v1/admin/source-policies/{policy_id}", {
          params: { path: { policy_id: editing.value.id } },
          body: { ...draft, expected_revision: editing.value.revision },
        }),
      );
    } else {
      unwrap(
        await client.POST("/api/v1/admin/source-policies", { body: draft }),
      );
    }
    editing.value = undefined;
    draft.domain = "";
    await policies.refetch();
  });
}
function edit(row: components["schemas"]["PolicyDTO"]) {
  editing.value = row;
  Object.assign(draft, {
    domain: row.domain,
    purpose: row.purpose,
    mode: row.mode,
    store_text: row.store_text,
    store_excerpt: row.store_excerpt,
    official_evidence: row.official_evidence,
    usage_basis: row.usage_basis,
  });
}
const resolution = ref("");
async function resolve(row: components["schemas"]["ReportDTO"]) {
  await act(async () => {
    unwrap(
      await client.POST(
        "/api/v1/admin/feedback-reports/{report_id}/resolution",
        {
          params: { path: { report_id: row.id } },
          headers: key(),
          body: {
            expected_revision: row.revision,
            status: "resolved",
            resolution: resolution.value,
          },
        },
      ),
    );
    await reports.refetch();
  });
}
</script>
<template>
  <h1>来源与运行维护</h1>
  <p class="subtitle">仅维护来源策略、汇总与用户主动提交的纠错内容。</p>
  <el-alert
    v-if="!allowed"
    title="此页面仅供管理员使用，你没有来源运营权限。"
    type="warning"
  /><template v-else
    ><el-alert
      v-if="overview.error.value || policies.error.value || reports.error.value"
      title="运营数据加载失败，请重新加载"
      type="error"
    /><el-button
      v-if="overview.error.value || policies.error.value || reports.error.value"
      @click="
        overview.refetch();
        policies.refetch();
        reports.refetch();
      "
      >重新加载</el-button
    >
    <el-alert v-if="error" type="error" :title="error" />
    <section class="panel">
      <h2>运行概览</h2>
      <p>Provider 配置：{{ overview.data.value?.providers }}</p>
      <p>队列：{{ overview.data.value?.queue_states }}</p>
      <p>失败类型：{{ overview.data.value?.failure_codes }}</p>
      <p>
        调用记录 {{ overview.data.value?.reserved_calls }} · 用量未知
        {{ overview.data.value?.unknown_usage_calls }}
      </p>
    </section>
    <section class="panel">
      <h2>{{ editing ? "编辑来源策略" : "新增来源策略" }}</h2>
      <el-form label-position="top"
        ><div class="grid">
          <el-form-item label="精确域名"
            ><el-input v-model="draft.domain" /></el-form-item
          ><el-form-item label="用途"
            ><el-select v-model="draft.purpose"
              ><el-option
                v-for="value in ['jobs', 'interview', 'knowledge']"
                :key="value"
                :value="value" /></el-select></el-form-item
          ><el-form-item label="访问模式"
            ><el-select v-model="draft.mode"
              ><el-option value="metadata_only" label="仅线索" /><el-option
                value="extract_allowed"
                label="允许提取" /><el-option
                value="disabled"
                label="禁用" /></el-select></el-form-item
          ><el-form-item label="使用依据"
            ><el-input
              v-model="draft.usage_basis"
              type="textarea" /></el-form-item
          ><el-form-item label="官方关联证据（没有则保持空）"
            ><el-input v-model="draft.official_evidence"
          /></el-form-item>
        </div>
        <el-checkbox v-model="draft.store_text">允许保存正文</el-checkbox
        ><el-checkbox v-model="draft.store_excerpt"
          >允许保存必要片段</el-checkbox
        >
        <p>
          <el-button type="primary" :loading="busy" @click="save"
            >保存策略</el-button
          >
        </p></el-form
      ><el-table :data="policies.data.value?.items ?? []"
        ><el-table-column prop="domain" label="域名" /><el-table-column
          prop="mode"
          label="模式"
        /><el-table-column prop="purpose" label="用途" /><el-table-column
          label="操作"
          ><template #default="scope"
            ><el-button link @click="edit(scope.row)">修改</el-button></template
          ></el-table-column
        ></el-table
      >
    </section>
    <section class="panel">
      <h2>用户纠错与举报</h2>
      <p class="muted">
        只显示主动提交的文本与片段，不提供任意查看个人简历或回答的入口。
      </p>
      <el-input
        v-model="resolution"
        type="textarea"
        placeholder="处理依据与结果"
      />
      <article
        v-for="report in reports.data.value?.items"
        :key="report.id"
        class="fact"
      >
        <el-tag>{{ report.status }}</el-tag>
        <p>{{ report.message }}</p>
        <blockquote v-if="report.shared_excerpt" class="evidence">
          {{ report.shared_excerpt }}
        </blockquote>
        <el-button :disabled="!resolution" @click="resolve(report)"
          >记录处理结果</el-button
        >
      </article>
    </section>
  </template>
</template>
