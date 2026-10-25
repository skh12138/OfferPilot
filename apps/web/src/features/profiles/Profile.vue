<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
const route = useRoute(),
  router = useRouter();
import { useDraft } from "../../app/ui";
import { useChoiceQuery } from "../../app/navigation";
import PageHeader from "../../components/PageHeader.vue";
import DraftDrawer from "../../components/DraftDrawer.vue";
import { label } from "../../utils/labels";
import { clone } from "../../api/clone";
import DataControls from "./DataControls.vue";
import ReportForm from "../../components/ReportForm.vue";
import { computed, ref, watch } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import type { components } from "../../api/schema";
import { client, unwrap, key } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
import RunStatus from "../../components/RunStatus.vue";
const session = useSession(),
  cache = useQueryClient(),
  { busy, error, act } = useAction();
const profile = useQuery({
  queryKey: ["profile", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/profiles/current")),
});
const consent = useQuery({
  queryKey: ["consent", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/me/model-consent")),
});
const resumes = useQuery({
  queryKey: ["resumes", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/resume-versions")),
});
const capabilities = useQuery({
  queryKey: ["capabilities"],
  queryFn: async () => unwrap(await client.GET("/api/v1/capabilities")),
});
const form = useDraft<components["schemas"]["ProfileInput"]>(
  "profile-edit",
  () => ({
    preferences: { notes: "", work_mode_is_hard: false },
    facts: [],
    reason: "人工确认与修改",
  }),
);
const draft = form.draft,
  editing = ref(false),
  importOpen = ref(false);
const tab = useChoiceQuery(
  "tab",
  ["preferences", "facts", "history", "privacy"],
  "facts",
);
const factFilter = useChoiceQuery(
  "fact_status",
  ["", "unconfirmed", "user_confirmed", "planned", "disputed"],
  "",
);
watch(
  () => profile.data.value?.current,
  (value) => {
    if (value && !form.dirty.value) {
      form.load({
        resume_version_id: value.resume_version_id,
        preferences: clone(value.preferences),
        facts: clone(value.facts),
        reason: "人工确认与修改",
      });
    }
  },
  { immediate: true },
);
const resumeForm = useDraft("resume-import", () => ({
  text: "",
  title: "我的简历",
}));
const text = computed({
    get: () => resumeForm.draft.value.text,
    set: (value) => {
      resumeForm.draft.value.text = value;
    },
  }),
  title = computed({
    get: () => resumeForm.draft.value.title,
    set: (value) => {
      resumeForm.draft.value.title = value;
    },
  }),
  runId = computed({
    get: () => String(route.query.run ?? ""),
    set: (run) => {
      void router.replace({ query: { ...route.query, run } });
    },
  }),
  pending = computed(
    () =>
      draft.value.facts?.filter((f) => f.status === "unconfirmed").length ?? 0,
  );
async function setConsent(granted: boolean) {
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/me/model-consent", { body: { granted } }),
    );
    await consent.refetch();
  });
}
async function parse() {
  await act(async () => {
    const result = unwrap(
      await client.POST("/api/v1/resume-versions", {
        body: { title: title.value, text: text.value, parse: true },
        headers: key(),
      }),
    );
    resumeForm.saved();
    importOpen.value = false;
    runId.value = result.id;
  });
}
async function save() {
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/profile-versions", { body: draft.value }),
    );
    form.saved();
    editing.value = false;
    await cache.invalidateQueries({ queryKey: ["profile", session.user?.id] });
  });
}
async function revoke(factId: string) {
  const current = profile.data.value?.current;
  if (!current) return;
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/profile-versions/{profile_id}/revocations", {
        params: { path: { profile_id: current.id } },
        body: { fact_id: factId, reason: "本人撤回" },
      }),
    );
    await cache.invalidateQueries();
  });
}
function newFactId() {
  return crypto.randomUUID();
}
function addFact() {
  draft.value.facts ??= [];
  draft.value.facts.push({
    fact_id: crypto.randomUUID(),
    text: "",
    status: "unconfirmed",
    evidence: {
      paragraph_id: "user",
      quote: "本人补充",
      source_kind: "user_asserted",
    },
  });
}

async function saveText() {
  await act(async () => {
    const result = unwrap(
      await client.POST("/api/v1/resume-versions", {
        body: { title: title.value, text: text.value, parse: false },
        headers: key(),
      }),
    );
    if ("text" in result) {
      resumeForm.saved();
      importOpen.value = false;
      draft.value.resume_version_id = result.id;
      await resumes.refetch();
    }
  });
}
</script>
<template>
  <PageHeader title="我的资料" description="确认真实做过的事，保留每个版本。"
    ><el-button type="primary" @click="importOpen = true"
      >导入简历</el-button
    ></PageHeader
  ><el-alert
    v-if="
      profile.error.value ||
      resumes.error.value ||
      consent.error.value ||
      (error && !importOpen)
    "
    :title="error || '资料加载失败，请重试'"
    type="error"
  /><el-button
    v-if="profile.error.value || resumes.error.value || consent.error.value"
    @click="
      profile.refetch();
      resumes.refetch();
      consent.refetch();
    "
    >重新加载资料</el-button
  ><el-skeleton v-if="profile.isPending.value" animated />
  <RunStatus
    v-if="runId"
    :id="runId"
    @complete="
      profile.refetch();
      resumes.refetch();
    "
  />
  <el-tabs v-model="tab"
    ><el-tab-pane label="求职偏好" name="preferences">
      <section class="panel">
        <h2>求职条件与偏好</h2>
        <div v-if="!editing" class="definition-grid">
          <p>
            目标岗位：{{
              profile.data.value?.current?.preferences.target_roles?.join(
                "、",
              ) || "未提供"
            }}
          </p>
          <p>
            城市：{{
              profile.data.value?.current?.preferences.cities?.join("、") ||
              "未提供"
            }}
          </p>
          <p>
            每周天数：{{
              profile.data.value?.current?.preferences.days_per_week ?? "未提供"
            }}
          </p>
          <p>
            可持续时长：{{
              profile.data.value?.current?.preferences.duration_months ??
              "未提供"
            }}
            日历月
          </p>
          <p>
            学历：{{
              label(
                profile.data.value?.current?.preferences.education ?? "未提供",
              )
            }}
          </p>
          <p>
            毕业年份：{{
              profile.data.value?.current?.preferences.graduation_year ??
              "未提供"
            }}
          </p>
        </div>
        <el-button v-if="!editing" @click="editing = true"
          >编辑求职条件与事实</el-button
        >
        <el-form v-if="editing" label-position="top"
          ><div class="grid">
            <el-form-item label="目标岗位"
              ><el-select
                v-model="draft.preferences.target_roles"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="输入岗位后回车" /></el-form-item
            ><el-form-item label="可到岗城市"
              ><el-select
                v-model="draft.preferences.cities"
                multiple
                filterable
                allow-create
                default-first-option /></el-form-item
            ><el-form-item label="每周最多可到岗天数"
              ><el-input-number
                v-model="draft.preferences.days_per_week"
                :min="1"
                :max="7" /></el-form-item
            ><el-form-item label="可持续时长（日历月）"
              ><el-input-number
                v-model="draft.preferences.duration_months"
                :min="1"
                :max="60" /></el-form-item
            ><el-form-item label="毕业年份"
              ><el-input-number
                v-model="draft.preferences.graduation_year"
                :min="2000"
                :max="2100" /></el-form-item
            ><el-form-item label="学历"
              ><el-select v-model="draft.preferences.education" clearable
                ><el-option
                  v-for="[value, label] in [
                    ['associate', '专科'],
                    ['bachelor', '本科'],
                    ['master', '硕士'],
                    ['doctor', '博士'],
                  ]"
                  :key="value"
                  :value="value"
                  :label="label" /></el-select
            ></el-form-item></div
        ></el-form>
      </section>
      <el-button v-if="editing" type="primary" :loading="busy" @click="save"
        >保存新的资料版本</el-button
      ></el-tab-pane
    ><el-tab-pane label="简历与事实" name="facts">
      <section class="panel">
        <h2>
          事实校对 <el-tag>{{ pending }} 条待确认</el-tag>
        </h2>
        <p class="muted">
          每条需要本人选择状态。修改正文会形成新的事实；被撤回的 ID
          不能用于新生成。
        </p>
        <div class="toolbar">
          <el-button v-if="!editing" @click="editing = true"
            >编辑资料与事实</el-button
          ><el-select
            v-model="factFilter"
            aria-label="事实状态筛选"
            placeholder="全部事实"
            clearable
            ><el-option value="unconfirmed" label="待确认" /><el-option
              value="user_confirmed"
              label="本人确认做过" /><el-option
              value="planned"
              label="计划中" /><el-option value="disputed" label="有争议"
          /></el-select>
        </div>
        <div v-if="!editing">
          <article
            class="fact"
            v-for="fact in profile.data.value?.current?.facts.filter(
              (f) => !factFilter || f.status === factFilter,
            )"
            :key="fact.fact_id"
          >
            <p>{{ fact.text }}</p>
            <el-tag>{{ label(fact.status) }}</el-tag>
            <blockquote class="evidence">{{ fact.evidence.quote }}</blockquote>
          </article>
          <p v-if="!profile.data.value?.current?.facts.length" class="muted">
            尚无事实，导入简历或点击编辑后补充。
          </p>
        </div>
        <template v-if="editing"
          ><p class="muted">
            未提交草稿仅在本次登录会话保留；后台更新不会覆盖输入。保存会创建新版本。
          </p>
          <div
            v-for="fact in draft.facts?.filter(
              (f) => !factFilter || f.status === factFilter,
            )"
            :key="fact.fact_id"
            class="fact"
          >
            <el-tag
              v-if="
                profile.data.value?.current?.revoked_fact_ids.includes(
                  fact.fact_id,
                )
              "
              type="danger"
              >此事实已撤回 / 有争议，不能用于新生成</el-tag
            ><el-input
              v-model="fact.text"
              type="textarea"
              :rows="2"
              aria-label="事实正文"
              @change="
                fact.fact_id = newFactId();
                fact.evidence.source_kind = 'user_asserted';
                fact.evidence.quote = fact.text;
              "
            />
            <div class="toolbar">
              <el-select v-model="fact.status" aria-label="事实状态"
                ><el-option
                  v-for="[value, label] in [
                    ['unconfirmed', '待确认'],
                    ['user_confirmed', '本人确认做过'],
                    ['planned', '计划中'],
                    ['disputed', '有争议'],
                  ]"
                  :key="value"
                  :value="value"
                  :label="label" /></el-select
              ><el-button link type="danger" @click="revoke(fact.fact_id)"
                >撤回原事实</el-button
              >
            </div>
            <blockquote class="evidence">
              {{ fact.evidence.paragraph_id }} · {{ fact.evidence.quote }}
            </blockquote>
          </div>
          <div class="toolbar">
            <el-button @click="addFact">补充事实</el-button
            ><el-button type="primary" :loading="busy" @click="save"
              >保存新的资料版本</el-button
            >
          </div>
        </template>
      </section> </el-tab-pane
    ><el-tab-pane label="版本记录" name="history">
      <section class="panel">
        <h2>版本历史</h2>
        <p v-if="!profile.data.value?.versions.length" class="empty">
          尚无资料版本
        </p>
        <p v-for="version in profile.data.value?.versions" :key="version.id">
          {{ version.created_at }} · {{ version.reason }} ·
          {{
            version.unavailable
              ? "资料已删除"
              : `${version.facts.length} 条事实`
          }}
        </p>
        <p v-for="resume in resumes.data.value?.items" :key="resume.id">
          {{ resume.title }} ·
          {{ resume.deleted_at ? "资料已删除" : resume.created_at }}
        </p>
      </section> </el-tab-pane
    ><el-tab-pane label="授权与数据控制" name="privacy">
      <section class="panel">
        <h2>外部模型处理授权</h2>
        <p>
          解析简历、准备材料、定制练习与反馈会向配置的模型服务发送必要正文。公开搜索的独立授权在找岗页设置，不读取个人简历。撤销后将停止新的模型调用；已发送内容受提供商政策约束。
        </p>
        <el-button
          v-if="!consent.data.value?.granted"
          type="primary"
          @click="setConsent(true)"
          >同意必要的外部模型处理</el-button
        ><el-button v-else @click="setConsent(false)">撤销授权</el-button>
      </section>
      <DataControls /></el-tab-pane
  ></el-tabs>
  <DraftDrawer
    v-model="importOpen"
    title="导入简历文本"
    :dirty="resumeForm.dirty.value"
    :busy="busy"
  >
    <el-alert v-if="error" :title="error" type="error" />
    <el-form label-position="top"
      ><el-form-item label="版本标题"
        ><el-input v-model="title" aria-label="简历标题" /></el-form-item
      ><el-form-item label="纯文本，最多 50000 字符"
        ><el-input
          v-model="text"
          type="textarea"
          :rows="7"
          maxlength="50000"
          aria-label="简历文本" /></el-form-item
      ><el-button
        type="primary"
        :loading="busy"
        :disabled="
          !text ||
          !consent.data.value?.granted ||
          !capabilities.data.value?.model_available
        "
        @click="parse"
        >解析并保存新简历</el-button
      ><el-button :loading="busy" :disabled="!text" @click="saveText"
        >仅保存文本，暂不解析</el-button
      ></el-form
    >
  </DraftDrawer>
  <ReportForm kind="other" />
</template>
