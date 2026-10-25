<script setup lang="ts">
import { useUi } from "../../app/ui";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { client, key, unwrap } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
import type { components } from "../../api/schema";
import RunStatus from "../../components/RunStatus.vue";
const ui = useUi();
const session = useSession(),
  cache = useQueryClient(),
  route = useRoute(),
  router = useRouter(),
  { busy, error, act } = useAction();
const exportId = computed({
    get: () => String(route.query.export ?? ""),
    set: (value) => {
      void router.replace({ query: { ...route.query, export: value } });
    },
  }),
  preview = ref<components["schemas"]["DeletePreview"]>(),
  showDelete = ref(false),
  deleteId = ref(""),
  accountDialog = ref(false),
  password = ref(""),
  accountConfirmed = ref(false),
  receipt = ref("");
const resumes = useQuery({
  queryKey: ["resumes", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/resume-versions")),
});
const exported = useQuery({
  queryKey: computed(() => ["export", session.user?.id, exportId.value]),
  enabled: computed(() => !!exportId.value),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/me/exports/{export_id}", {
        params: { path: { export_id: exportId.value } },
      }),
    ),
  refetchInterval: (query) =>
    query.state.data?.status === "queued" ? 1500 : false,
});
const deletion = useQuery({
  queryKey: computed(() => ["deletion", deleteId.value]),
  enabled: computed(() => !!deleteId.value),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/deletion-requests/{deletion_id}", {
        params: { path: { deletion_id: deleteId.value } },
        headers: receipt.value
          ? { "X-Deletion-Receipt": receipt.value }
          : undefined,
      }),
    ),
  refetchInterval: (query) =>
    query.state.data?.status === "succeeded" ? false : 1500,
});
async function createExport(format: "json" | "csv") {
  await act(async () => {
    const row = unwrap(
      await client.POST("/api/v1/me/exports", {
        body: { format },
        headers: key(),
      }),
    );
    exportId.value = row.id;
  });
}
async function deletionPreview(id: string) {
  await act(async () => {
    preview.value = unwrap(
      await client.GET("/api/v1/resume-versions/{resume_id}/deletion-preview", {
        params: { path: { resume_id: id } },
      }),
    );
    showDelete.value = true;
  });
}
async function deleteResume() {
  const p = preview.value;
  if (!p) return;
  await act(async () => {
    const row = unwrap(
      await client.DELETE("/api/v1/resume-versions/{resume_id}", {
        params: { path: { resume_id: p.resume_id } },
        body: { confirmed: true },
        headers: key(),
      }),
    );
    deleteId.value = row.id;
    showDelete.value = false;
    ui.clearPersonal();
    await cache.invalidateQueries();
  });
}
async function deleteAccount() {
  await act(async () => {
    const row = unwrap(
      await client.DELETE("/api/v1/me", {
        body: { password: password.value, confirmed: accountConfirmed.value },
        headers: key(),
      }),
    );
    receipt.value = row.receipt ?? "";
    deleteId.value = row.id;
    password.value = "";
    accountDialog.value = false;
    ui.clear();
    session.user = undefined;
    cache.clear();
  });
}
</script>
<template>
  <section class="panel">
    <h2>数据控制</h2>
    <el-alert v-if="error" type="error" :title="error" />
    <p>
      导出只属于本人，下载有效期 24
      小时。删除简历会清理引用它的材料、训练、回答、反馈与步骤结果；申请保留最小历史墓碑。
    </p>
    <div class="toolbar">
      <el-button :loading="busy" @click="createExport('json')"
        >导出本人 JSON</el-button
      ><el-button :loading="busy" @click="createExport('csv')"
        >导出岗位 CSV</el-button
      ><el-button type="danger" plain @click="accountDialog = true"
        >删除账户</el-button
      >
    </div>
    <div v-if="exported.data.value">
      <p>
        导出状态：{{ exported.data.value.status }} · 有效至
        {{ exported.data.value.expires_at }}
      </p>
      <a
        v-if="exported.data.value.status === 'succeeded'"
        :href="`/api/v1/me/exports/${exportId}/download`"
        download
        >下载本人数据</a
      ><RunStatus
        v-if="
          exported.data.value.run_id && exported.data.value.status === 'queued'
        "
        :id="exported.data.value.run_id"
        @complete="exported.refetch()"
      />
    </div>
    <p v-for="resume in resumes.data.value?.items" :key="resume.id">
      {{ resume.title }}
      <el-button
        v-if="!resume.deleted_at"
        link
        type="danger"
        @click="deletionPreview(resume.id)"
        >查看影响并删除这份简历</el-button
      ><span v-else>资料已删除</span>
    </p>
    <div v-if="deleteId">
      <p>
        清理状态：{{ deletion.data.value?.status ?? "正在读取" }}；仅显示
        succeeded 才表示当前应用数据清理完毕。
      </p>
      <p v-if="receipt" class="evidence">
        账户删除回执（请自行保管）：{{ receipt }}<br />请求编号：{{ deleteId }}
      </p>
      <RunStatus
        v-if="
          deletion.data.value?.run_id &&
          deletion.data.value.status !== 'succeeded' &&
          !receipt
        "
        :id="deletion.data.value.run_id"
        @complete="deletion.refetch()"
      />
    </div>
    <p class="muted">
      未配置自管备份。已发送给模型提供商的数据无法由本应用保证即时撤回。
    </p>
  </section>
  <el-dialog v-model="showDelete" title="确认删除影响范围"
    ><template v-if="preview"
      ><p>
        将清理 {{ preview.profile_versions }} 个资料版本、{{
          preview.material_versions
        }}
        个材料版本、{{ preview.study_versions }} 个训练版本，并停止
        {{ preview.active_runs }} 个关联活动。
      </p>
      <p v-for="note in preview.preserved" :key="note">{{ note }}</p>
      <p>
        同时清除当前会话中资料、材料与练习的未提交草稿，其他普通待办草稿保留。
      </p>
      <el-button type="danger" :loading="busy" @click="deleteResume"
        >确认删除并清理衍生内容</el-button
      ></template
    ></el-dialog
  ><el-dialog v-model="accountDialog" title="删除整个账户"
    ><p>
      普通会话会立即撤销，所有本人资料和私有运行记录将由后台清理。清理进度仅能凭回执查询。
    </p>
    <el-form label-position="top"
      ><el-form-item label="再次验证密码"
        ><el-input
          v-model="password"
          type="password"
          autocomplete="current-password" /></el-form-item
      ><el-checkbox v-model="accountConfirmed"
        >确认删除整个账户及所有本人数据</el-checkbox
      >
      <p>
        <el-button
          type="danger"
          :loading="busy"
          :disabled="!password || !accountConfirmed"
          @click="deleteAccount"
          >验证并删除账户</el-button
        >
      </p></el-form
    ></el-dialog
  >
</template>
