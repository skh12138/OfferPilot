<script setup lang="ts">
import AsyncState from "../../components/AsyncState.vue";
import SplitPreview from "../../components/SplitPreview.vue";
import JobReading from "./JobReading.vue";
import DraftDrawer from "../../components/DraftDrawer.vue";
import { useTextQuery, useWide, useListPosition } from "../../app/navigation";
import { useDraft } from "../../app/ui";
import DuplicatePanel from "./DuplicatePanel.vue";
import { label, preferenceLabel } from "../../utils/labels";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQuery } from "@tanstack/vue-query";
import { client, unwrap, key } from "../../api/client";
import { useAction } from "../../app/action";
import { useSession } from "../../app/session";
import RunStatus from "../../components/RunStatus.vue";
import type { components } from "../../api/schema";
const route = useRoute(),
  router = useRouter(),
  session = useSession(),
  { busy, error, act } = useAction();
const q = computed({
  get: () => String(route.query.q ?? ""),
  set: (value) => {
    void router.replace({
      query: { ...route.query, q: value || undefined, cursor: undefined },
    });
  },
});
function filter(name: string) {
  return computed({
    get: () => String(route.query[name] ?? ""),
    set: (value: string) => {
      void router.replace({
        query: {
          ...route.query,
          [name]: value || undefined,
          cursor: undefined,
        },
      });
    },
  });
}
const preference = filter("preference"),
  risk = filter("risk"),
  eligibility = filter("eligibility");
const jobs = useQuery({
  queryKey: computed(() => [
    "jobs",
    session.user?.id,
    q.value,
    preference.value,
    risk.value,
    eligibility.value,
    route.query.cursor,
  ]),
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/jobs", {
        params: {
          query: {
            q: q.value,
            preference: preference.value || undefined,
            risk: risk.value || undefined,
            eligibility: eligibility.value || undefined,
            cursor: route.query.cursor ? String(route.query.cursor) : undefined,
          },
        },
      }),
    ),
});
const { input: searchInput, compositionStart, compositionEnd } = useTextQuery();
const wide = useWide();
useListPosition(computed(() => !jobs.isPending.value));
const preview = computed(
  () =>
    jobs.data.value?.items.find((j) => j.id === route.query.selected) ??
    (!route.query.selected && wide.value
      ? jobs.data.value?.items[0]
      : undefined),
);
function select(id: string) {
  void router.replace({ query: { ...route.query, selected: id } });
}
function clearFilters() {
  void router.replace({
    query: {
      ...route.query,
      q: undefined,
      preference: undefined,
      risk: undefined,
      eligibility: undefined,
      cursor: undefined,
      selected: undefined,
    },
  });
}
const importState = useDraft("job-import", () => ({
  text: "",
  url: "",
  format: "text" as "text" | "csv",
}));
const text = computed({
    get: () => importState.draft.value.text,
    set: (value) => {
      importState.draft.value.text = value;
    },
  }),
  url = computed({
    get: () => importState.draft.value.url,
    set: (value) => {
      importState.draft.value.url = value;
    },
  }),
  format = computed({
    get: () => importState.draft.value.format,
    set: (value) => {
      importState.draft.value.format = value;
    },
  }),
  runId = computed({
    get: () => String(route.query.run ?? ""),
    set: (run) => {
      void router.replace({ query: { ...route.query, run } });
    },
  }),
  showImport = ref(false),
  selected = computed<string[]>({
    get: () =>
      String(route.query.compare ?? "")
        .split(",")
        .filter((v) => /^[a-f0-9-]{36}$/.test(v))
        .slice(0, 4),
    set: (values) => {
      void router.replace({
        query: { ...route.query, compare: values.join(",") || undefined },
      });
    },
  }),
  comparison = ref<components["schemas"]["JobDTO"][]>([]);
async function submit() {
  await act(async () => {
    const run = unwrap(
      await client.POST("/api/v1/job-imports", {
        body: {
          text: text.value,
          url: url.value || null,
          format: format.value,
        },
        headers: key(),
      }),
    );
    runId.value = run.id;
    importState.saved();
    showImport.value = false;
  });
}
async function compare() {
  await act(async () => {
    comparison.value = unwrap(
      await client.POST("/api/v1/jobs/compare", {
        body: { ids: selected.value },
      }),
    );
  });
}

async function readCsv(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) {
    error.value = "CSV最多5MB";
    return;
  }
  format.value = "csv";
  text.value = await file.text();
}
</script>
<template>
  <h1>岗位库</h1>
  <p class="subtitle">按条件判断，回到来源核实，再决定下一步。</p>
  <div class="toolbar">
    <el-input
      v-model="searchInput"
      @compositionstart="compositionStart"
      @compositionend="compositionEnd"
      placeholder="筛选岗位 / 公司 / 城市"
      aria-label="筛选岗位"
      clearable
    /><el-button @click="showImport = true">导入文本 / CSV</el-button
    ><el-button
      :disabled="!selected.length || selected.length > 4"
      @click="compare"
      >比较 {{ selected.length }} / 4</el-button
    >
  </div>
  <div class="toolbar">
    <el-select
      v-model="preference"
      aria-label="意向筛选"
      placeholder="全部意向"
      clearable
    >
      <el-option
        v-for="[value, text] in [
          ['priority', '优先'],
          ['interested', '感兴趣'],
          ['unassigned', '未设置'],
          ['paused', '暂缓'],
          ['excluded', '已排除'],
        ]"
        :key="value"
        :value="value"
        :label="text"
      />
    </el-select>
    <el-select
      v-model="eligibility"
      aria-label="资格筛选"
      placeholder="全部资格状态"
      clearable
    >
      <el-option
        v-for="[value, text] in [
          ['pass', '条件通过'],
          ['fail', '存在不符'],
          ['unknown', '仍需核实'],
        ]"
        :key="value"
        :value="value"
        :label="text"
      />
    </el-select>
    <el-select
      v-model="risk"
      aria-label="风险筛选"
      placeholder="默认隐藏高风险提示"
      clearable
    >
      <el-option
        v-for="[value, text] in [
          ['unknown', '风险未知'],
          ['no_known_flags', '暂无已知风险提示'],
          ['high_risk_flag', '查看高风险提示岗位'],
        ]"
        :key="value"
        :value="value"
        :label="text"
      />
    </el-select>
  </div>
  <el-alert v-if="error && !showImport" type="error" :title="error" /><RunStatus
    v-if="runId"
    :id="runId"
    @complete="jobs.refetch()"
  /><AsyncState
    :pending="jobs.isPending.value"
    :error="jobs.error.value"
    :empty="!jobs.data.value?.items.length"
    :message="
      jobs.error.value
        ? '岗位加载失败，请检查连接后重试'
        : q || preference || risk || eligibility
          ? '没有匹配筛选的岗位'
          : '还没有岗位'
    "
    @retry="jobs.refetch()"
    ><el-button
      v-if="q || preference || risk || eligibility"
      @click="clearFilters"
      >清空筛选</el-button
    ><RouterLink v-else to="/discover">开始找岗位 →</RouterLink></AsyncState
  >
  <DuplicatePanel @saved="jobs.refetch()" />
  <p class="muted">
    当前已加载 {{ jobs.data.value?.items.length ?? 0 }} 条岗位<span
      v-if="jobs.isFetching.value && !jobs.isPending.value"
    >
      · 正在更新</span
    >
  </p>
  <div v-if="preference || risk || eligibility || q" class="filter-chips">
    <el-tag v-if="q" closable @close="searchInput = ''">关键词：{{ q }}</el-tag
    ><el-tag v-if="preference" closable @close="preference = ''"
      >意向：{{ label(preference) }}</el-tag
    ><el-tag v-if="eligibility" closable @close="eligibility = ''"
      >资格：{{ label(eligibility) }}</el-tag
    ><el-tag v-if="risk" closable @close="risk = ''"
      >风险：{{ label(risk) }}</el-tag
    ><el-button text @click="clearFilters">清空筛选</el-button>
  </div>
  <div v-if="selected.length" class="selection-bar" aria-label="岗位比较选择">
    <strong>已选 {{ selected.length }} / 4</strong
    ><el-tag
      v-for="id in selected"
      :key="id"
      closable
      @close="selected = selected.filter((v) => v !== id)"
      >{{
        jobs.data.value?.items.find((j) => j.id === id)?.current?.data.title ||
        id.slice(0, 8)
      }}</el-tag
    ><el-button @click="compare" :loading="busy">进入比较</el-button
    ><el-button text @click="selected = []">清空比较</el-button>
  </div>
  <SplitPreview
    v-if="jobs.data.value?.items.length"
    :selected="!!preview"
    @close="router.replace({ query: { ...route.query, selected: undefined } })"
  >
    <article
      v-for="job in jobs.data.value.items"
      :key="job.id"
      class="flat-row"
      :class="{ 'is-selected': preview?.id === job.id }"
      :aria-label="`岗位：${job.current?.data.title}`"
    >
      <div class="row-top">
        <span class="eyebrow">{{
          job.current?.data.company || "公司待核实"
        }}</span
        ><el-checkbox
          v-model="selected"
          :value="job.id"
          :disabled="selected.length >= 4 && !selected.includes(job.id)"
          :aria-label="`比较 ${job.current?.data.title}`"
          >加入比较</el-checkbox
        >
      </div>
      <h2>
        <RouterLink :to="`/jobs/${job.id}`">{{
          job.current?.data.title
        }}</RouterLink>
      </h2>
      <div class="row-meta">
        <span>{{ job.current?.data.cities?.join(" / ") || "地点待核实" }}</span
        ><span>{{ job.current?.data.salary?.raw || "薪资未提供" }}</span
        ><span>意向：{{ preferenceLabel(job.preference) }}</span>
      </div>
      <p class="row-summary">
        {{
          job.current?.data.requirements
            ?.slice(0, 2)
            .map((r) => r.text)
            .join("；") || "要求待核实"
        }}
      </p>
      <div class="row-bottom">
        <span class="row-status"
          >{{ label(job.verification?.source_status || "unknown") }} · 资格{{
            label(job.eligibility)
          }}<span v-if="preview?.id === job.id"> · 已选中</span></span
        ><el-button
          text
          :aria-label="`预览${job.current?.data.title}`"
          @click="select(job.id)"
          >预览 →</el-button
        >
      </div>
    </article>
    <template #preview
      ><JobReading v-if="preview" :job="preview" /><RouterLink
        v-if="preview"
        :to="`/jobs/${preview.id}`"
        >打开详情、校对与个人意向 →</RouterLink
      ></template
    >
  </SplitPreview>
  <div class="toolbar">
    <el-button
      @click="router.replace({ query: { ...route.query, cursor: undefined } })"
      >第一页</el-button
    ><el-button
      :disabled="!jobs.data.value?.has_more"
      @click="
        router.replace({
          query: {
            ...route.query,
            cursor: jobs.data.value?.next_cursor ?? undefined,
          },
        })
      "
      >下一页</el-button
    >
  </div>
  <section v-if="comparison.length" class="panel">
    <h2>岗位比较</h2>
    <el-table :data="comparison"
      ><el-table-column label="岗位"
        ><template #default="scope">{{
          scope.row.current?.data.title
        }}</template></el-table-column
      ><el-table-column label="城市"
        ><template #default="scope">{{
          scope.row.current?.data.cities?.join(" / ")
        }}</template></el-table-column
      ><el-table-column label="薪资原文"
        ><template #default="scope">{{
          scope.row.current?.data.salary.raw || "待核实"
        }}</template></el-table-column
      ></el-table
    >
  </section>
  <DraftDrawer
    v-model="showImport"
    title="导入岗位"
    :dirty="importState.dirty.value"
    :busy="busy"
    ><el-alert v-if="error" :title="error" type="error" /><el-form
      label-position="top"
      ><el-form-item label="导入格式"
        ><el-radio-group v-model="format"
          ><el-radio-button value="text">JD 文本</el-radio-button
          ><el-radio-button value="csv"
            >CSV（text,url 列）</el-radio-button
          ></el-radio-group
        ></el-form-item
      ><el-form-item label="CSV 文件（最多5MB / 500行）"
        ><input
          type="file"
          accept=".csv,text/csv"
          aria-label="CSV 文件"
          @change="readCsv" /></el-form-item
      ><el-form-item label="岗位正文 / CSV 内容"
        ><el-input
          v-model="text"
          type="textarea"
          :rows="10"
          aria-label="岗位正文" /></el-form-item
      ><el-form-item label="来源链接（可空）"
        ><el-input v-model="url" aria-label="岗位来源" /></el-form-item
      ><el-alert
        title="内容标为用户提供，不自动认定官方来源或已投递。"
        :closable="false"
      /><el-button
        type="primary"
        :loading="busy"
        :disabled="!text"
        @click="submit"
        >解析岗位</el-button
      ></el-form
    ></DraftDrawer
  >
</template>
