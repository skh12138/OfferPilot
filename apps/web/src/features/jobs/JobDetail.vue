<script setup lang="ts">
import JobReading from "./JobReading.vue";
import { useDraft, useUi } from "../../app/ui";
import { ElMessageBox } from "element-plus";
import PreferenceControls from "./PreferenceControls.vue";
import { label } from "../../utils/labels";
import { clone } from "../../api/clone";
import ReportForm from "../../components/ReportForm.vue";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQuery } from "@tanstack/vue-query";
import { client, unwrap, key } from "../../api/client";
import type { components } from "../../api/schema";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
const router = useRouter();
const route = useRoute(),
  id = computed(() => String(route.params.id)),
  session = useSession(),
  { busy, error, act } = useAction();
const job = useQuery({
  queryKey: computed(() => ["job", session.user?.id, id.value]),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/jobs/{job_id}", {
        params: { path: { job_id: id.value } },
      }),
    ),
});
const profile = useQuery({
  queryKey: ["profile", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/profiles/current")),
});
const ui = useUi(),
  editing = ref(false);
const form = useDraft<{
  data?: components["schemas"]["JobExtraction-Output"];
  revision?: number;
}>(
  () => "job:" + id.value,
  () => ({}),
);
const draft = computed({
    get: () => form.draft.value.data,
    set: (value) => {
      form.draft.value.data = value;
    },
  }),
  report = ref<components["schemas"]["MatchDTO"]>();
function loadCurrent() {
  const data = job.data.value?.current;
  if (!data) return;
  draft.value = clone(data.data);
  form.draft.value.revision = job.data.value?.revision;
  draft.value.conditions ??= {};
  for (const name of [
    "days_per_week",
    "duration_months",
    "graduation_year",
    "cities",
    "education",
    "work_mode",
  ]) {
    draft.value.conditions[name] ??= {
      value: null,
      review_status: "missing",
      strength: "hard",
      evidence_status: "unsupported",
      unrestricted: false,
      unit: name === "duration_months" ? "calendar_month" : null,
    };
  }
  form.saved();
}
watch(
  () => job.data.value?.current,
  (data) => {
    if (data && !form.dirty.value) loadCurrent();
  },
  { immediate: true },
);
async function discardAndReload() {
  try {
    await ElMessageBox.confirm(
      "将放弃本地未保存修改，载入服务器当前字段。",
      "载入最新字段？",
      {
        confirmButtonText: "放弃草稿并载入",
        cancelButtonText: "继续编辑",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  await job.refetch();
  loadCurrent();
}
function updateCondition(name: string, value: string) {
  const condition = draft.value?.conditions?.[name];
  if (!condition) return;
  condition.value = !value.trim()
    ? null
    : ["days_per_week", "duration_months"].includes(name)
      ? Number(value)
      : ["cities", "graduation_year"].includes(name)
        ? value
            .split(/[,，、]/)
            .map((v) => v.trim())
            .filter(Boolean)
        : value;
  condition.review_status = value.trim() ? "unreviewed" : "missing";
}
async function confirm() {
  const data = draft.value,
    row = job.data.value;
  if (!data || !row) return;
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/jobs/{job_id}/versions", {
        params: { path: { job_id: id.value } },
        body: {
          data,
          expected_revision: form.draft.value.revision ?? row.revision,
          reason: "本人校对字段",
          confirm_fields: true,
        },
      }),
    );
    form.saved();
    editing.value = false;
    await job.refetch();
  });
}
async function match() {
  const version = job.data.value?.current_version_id;
  if (!version) return;
  await act(async () => {
    report.value = unwrap(
      await client.POST("/api/v1/matches", {
        body: {
          job_version_id: version,
          profile_version_id: profile.data.value?.current?.id ?? null,
        },
      }),
    );
  });
}

async function apply() {
  const row = job.data.value;
  if (!row?.current) return;
  await act(async () => {
    const app = unwrap(
      await client.POST("/api/v1/applications", {
        headers: key(),
        body: {
          allow_reapply: false,
          navigation_hint: "",
          title: row.current?.data.title ?? "岗位",
          company: row.current?.data.company ?? "待核实",
          job_version_id: row.current_version_id,
          profile_version_id: profile.data.value?.current?.id ?? null,
          job_url: row.sources[0]?.canonical_url ?? null,
        },
      }),
    );
    await router.push("/applications/" + app.id);
  });
}
</script>
<template>
  <RouterLink :to="ui.returns.jobs || ui.lists['/jobs'] || '/jobs'">{{
    ui.returns.jobs?.startsWith("/discover") ? "← 找岗位" : "← 岗位库"
  }}</RouterLink
  ><el-skeleton v-if="job.isPending.value" animated /><el-alert
    v-if="error || job.error.value"
    type="error"
    :title="error || '读取失败'"
  /><el-button v-if="job.error.value" @click="job.refetch()"
    >重新加载岗位</el-button
  ><template v-if="job.data.value && draft"
    ><h1 class="detail-title" style="margin-top: 20px">
      {{ job.data.value.current?.data.title }}
    </h1>
    <p class="subtitle">
      {{ draft.company }} · {{ draft.cities?.join(" / ") || "城市待核实" }}
    </p>
    <div class="tags">
      <el-tag>{{
        label(job.data.value.verification?.source_status ?? "待核实")
      }}</el-tag
      ><el-tag type="info">{{
        label(job.data.value.verification?.availability_status ?? "待核实")
      }}</el-tag
      ><el-tag type="warning">{{
        label(job.data.value.verification?.risk_status ?? "待核实")
      }}</el-tag>
    </div>
    <div class="toolbar">
      <el-button v-if="error" @click="job.refetch()">查看最新岗位版本</el-button
      ><el-button v-if="editing && form.dirty.value" @click="discardAndReload"
        >放弃草稿，载入最新字段</el-button
      >
      <el-button type="primary" :disabled="busy" @click="apply"
        >加入申请档案</el-button
      >
      <el-button :loading="busy" @click="match">检查条件匹配</el-button
      ><el-button @click="editing = !editing">{{
        editing ? "收起校对" : "校对字段"
      }}</el-button>
    </div>
    <el-collapse
      ><el-collapse-item title="个人意向与理由"
        ><PreferenceControls
          :job-id="id"
          @saved="job.refetch()" /></el-collapse-item></el-collapse
    ><JobReading :job="job.data.value" />
    <div v-show="editing" class="detail-grid">
      <section class="panel">
        <h2>字段校对</h2>
        <el-form label-position="top"
          ><el-form-item label="标题"
            ><el-input v-model="draft.title" /></el-form-item
          ><el-form-item label="公司"
            ><el-input v-model="draft.company"
          /></el-form-item>
          <div
            v-for="(condition, name) in draft.conditions"
            :key="name"
            class="fact"
          >
            <strong>{{ label(name ?? "待核实") }}</strong>
            <p>
              {{ condition.value ?? "未说明" }} ·
              {{ label(condition.strength ?? "待核实") }} ·
              {{ label(condition.review_status ?? "待核实") }}
            </p>
            <el-input
              :model-value="
                Array.isArray(condition.value)
                  ? condition.value.join('、')
                  : String(condition.value ?? '')
              "
              :aria-label="`${label(name ?? '')}条件值`"
              placeholder="空白表示缺失；多个城市或年份用顿号分隔"
              @update:model-value="updateCondition(String(name), $event)"
            />
            <el-select v-model="condition.strength" aria-label="约束强度"
              ><el-option value="hard" label="硬条件" /><el-option
                value="preferred"
                label="优先" /><el-option value="negotiable" label="可协商"
            /></el-select>
            <el-checkbox v-model="condition.unrestricted"
              >本人核实明确不限</el-checkbox
            >
            <blockquote v-if="condition.evidence" class="evidence">
              {{ condition.evidence.quote }}
            </blockquote>
            <el-select v-model="condition.review_status"
              ><el-option value="confirmed" label="确认" /><el-option
                value="unreviewed"
                label="待确认" /><el-option
                value="conflict"
                label="有冲突" /><el-option value="missing" label="缺失"
            /></el-select>
          </div>
          <el-button type="primary" :loading="busy" @click="confirm"
            >校对并保存新岗位版本</el-button
          ></el-form
        >
        <h2 style="margin-top: 24px">历史版本</h2>
        <p v-for="version in job.data.value.versions" :key="version.id">
          {{ version.created_at }} · {{ version.reason }}
        </p>
      </section>
      <section class="panel">
        <h2>来源与原文证据</h2>
        <p v-for="source in job.data.value.sources" :key="source.id">
          <a
            :href="source.canonical_url"
            target="_blank"
            rel="noopener noreferrer"
            >打开 {{ source.board }} 原站 ↗</a
          >
          <a
            v-for="alias in source.aliases"
            :key="alias"
            :href="alias"
            target="_blank"
            rel="noopener noreferrer"
            >其他已发现入口 ↗</a
          >
        </p>
        <el-collapse
          ><el-collapse-item
            v-for="snapshot in job.data.value.snapshots"
            :key="snapshot.id"
            :title="
              snapshot.kind === 'provider_extracted'
                ? '提供商提取文本快照'
                : '用户提供文本'
            "
            ><div
              v-for="(paragraph, name) in snapshot.paragraphs"
              :key="name"
              class="evidence"
            >
              {{ label(name ?? "待核实") }} · {{ paragraph }}
            </div></el-collapse-item
          ></el-collapse
        >
        <p class="muted">未写明的条件保持未知；来源存在不代表仍有名额。</p>
      </section>
    </div>
    <section v-if="report" class="panel">
      <h2>条件结果：{{ label(report.overall ?? "待核实") }}</h2>
      <p v-for="check in report.checks" :key="check.key">
        <el-tag>{{ label(check.status ?? "待核实") }}</el-tag>
        {{ label(check.key ?? "待核实") }} · {{ check.reason }}
      </p>
      <p class="muted">匹配只覆盖已确认条件，不表示录用概率。</p>
    </section></template
  >
  <ReportForm kind="job" :id="id" />
</template>
