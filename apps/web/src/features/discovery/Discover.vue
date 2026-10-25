<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useWide } from "../../app/navigation";
import SplitPreview from "../../components/SplitPreview.vue";
import PageHeader from "../../components/PageHeader.vue";
import OpportunityRow from "./OpportunityRow.vue";
import { useDiscovery } from "./useDiscovery";
import OpportunityCard from "./OpportunityCard.vue";
import RunStatus from "../../components/RunStatus.vue";
const {
  text,
  publicConsent,
  difficulty,
  sort,
  scope,
  runId,
  progressId,
  progress,
  running,
  capability,
  specs,
  candidates,
  cards,
  visibleCards,
  leftovers,
  fullCount,
  draft,
  busy,
  error,
  naturalSearch,
  search,
  organize,
  intent,
  startIntent,
  saveIntent,
} = useDiscovery();
const route = useRoute(),
  router = useRouter(),
  wide = useWide(),
  advanced = ref(false),
  composing = ref(false),
  dismissed = ref(false);
const selected = computed(
  () =>
    visibleCards.value.find((c) => c.id === route.query.selected) ??
    (!route.query.selected && wide.value && !dismissed.value
      ? visibleCards.value[0]
      : undefined),
);
function preview(id: string) {
  dismissed.value = false;
  void router.replace({ query: { ...route.query, selected: id } });
}
function closePreview() {
  dismissed.value = true;
  void router.replace({ query: { ...route.query, selected: undefined } });
}
function resetFilters() {
  void router.replace({
    query: { ...route.query, difficulty: undefined, scope: undefined },
  });
}
function submit() {
  if (!composing.value) void naturalSearch();
}
</script>
<template>
  <PageHeader
    title="找到下一份值得投入的机会"
    description="让 AI 整理岗位，把时间留给准备。"
  />
  <el-alert v-if="error" :title="error" type="error" :closable="false" />
  <el-alert
    v-if="
      capability.data.value &&
      (!capability.data.value.search_available ||
        !capability.data.value.model_available)
    "
    title="搜索或模型服务尚未配置，暂时无法生成招聘卡片。"
    type="warning"
    :closable="false"
  />
  <section class="discovery-search">
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="描述你的目标"
        ><el-input
          v-model="text"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 3 }"
          @compositionstart="composing = true"
          @compositionend="composing = false"
          maxlength="500"
          aria-label="自然语言条件"
          placeholder="帮我找找杭州开发相关实习，优先 Python 或后端，要求不要太高"
      /></el-form-item>
      <div class="discovery-examples">
        <button
          v-for="example in [
            '杭州开发相关实习',
            '上海前端开发实习，Vue方向',
            '深圳Python后端实习',
          ]"
          :key="example"
          type="button"
          @click="text = example"
        >
          {{ example }} ↗
        </button>
        <el-button class="advanced-trigger" text @click="advanced = true"
          >高级条件</el-button
        >
      </div>
      <div class="discovery-submit">
        <el-checkbox v-model="publicConsent" aria-label="允许AI整理公开招聘信息"
          >允许 AI 处理本次搜索条件与公开招聘信息，不读取我的简历</el-checkbox
        ><el-button
          type="primary"
          size="large"
          native-type="submit"
          :loading="busy"
          :disabled="
            !text.trim() ||
            !publicConsent ||
            running ||
            composing ||
            !capability.data.value?.search_available ||
            !capability.data.value?.model_available
          "
          >AI 找岗位</el-button
        >
      </div>
    </el-form>
  </section>
  <RunStatus
    v-if="progressId"
    :id="progressId"
    compact
    @complete="candidates.refetch()"
  />
  <section v-if="runId" class="discovery-results" aria-live="polite">
    <div class="discovery-results-heading">
      <div>
        <h2>为你整理的招聘机会</h2>
        <p class="muted">
          {{ cards.length }} 个机会 · {{ fullCount }} 个已读正文 ·
          {{ candidates.data.value?.items.length ?? 0 }} 条搜索来源
        </p>
      </div>
      <el-button
        v-if="!running && candidates.data.value?.items.length"
        :loading="busy"
        :disabled="!publicConsent"
        @click="organize"
        >{{ cards.length ? "重新整理结果" : "AI 整理已有链接" }}</el-button
      >
    </div>
    <div v-if="cards.length" class="discovery-filters">
      <el-radio-group v-model="scope"
        ><el-radio-button value="recommended">推荐机会</el-radio-button
        ><el-radio-button value="all">全部结果</el-radio-button></el-radio-group
      ><el-select
        v-model="difficulty"
        placeholder="全部预测难度"
        clearable
        aria-label="预测难度筛选"
        ><el-option value="easy" label="入门友好" /><el-option
          value="medium"
          label="适中" /><el-option value="hard" label="偏难" /><el-option
          value="unknown"
          label="信息不足" /></el-select
      ><el-select v-model="sort" aria-label="机会排序"
        ><el-option value="relevance" label="相关性优先" /><el-option
          value="difficulty"
          label="预测难度从低到高" /><el-option
          value="detail"
          label="正文信息优先"
      /></el-select>
    </div>
    <el-alert
      v-if="candidates.error.value"
      title="招聘结果加载失败，点击重试"
      type="error"
      @click="candidates.refetch()"
    />
    <SplitPreview
      v-if="visibleCards.length"
      :selected="!!selected"
      @close="closePreview"
      ><OpportunityRow
        v-for="item in visibleCards"
        :key="item.id"
        :item="item"
        :selected="item.id === selected?.id"
        @preview="preview($event.id)" /><template #preview
        ><OpportunityCard
          v-if="selected"
          :item="selected"
          @save="startIntent" /></template
    ></SplitPreview>
    <div v-if="running && !cards.length" class="panel">
      <el-skeleton :rows="6" animated />
      <p class="muted">AI 正在提炼招聘信息，完成一批就会显示一批。</p>
    </div>
    <div
      v-else-if="
        !visibleCards.length &&
        !candidates.isPending.value &&
        !candidates.error.value
      "
      class="state-box"
    >
      <h3>
        {{
          cards.length ? "当前筛选下没有匹配机会" : "暂未整理出足够明确的职位"
        }}
      </h3>
      <p>
        {{
          cards.length
            ? "可以切换全部结果或调整难度筛选。"
            : "部分页面只有目录或摘要。可点击上方整理已有链接，或换一组更具体的岗位关键词。"
        }}
      </p>
      <el-button v-if="cards.length" @click="resetFilters">清空筛选</el-button>
    </div>
    <el-collapse v-if="leftovers.length" class="panel"
      ><el-collapse-item
        :title="`其他搜索线索（${leftovers.length}） · 目录、详情受限或未明确的结果`"
        name="clues"
        ><article
          v-for="candidate in leftovers"
          :key="candidate.id"
          class="result-line"
        >
          <a :href="candidate.url" target="_blank" rel="noopener noreferrer"
            >{{ candidate.title }} ↗</a
          >
          <p class="muted">
            {{
              candidate.intelligence?.note ||
              "尚未形成具体职位卡片，请到来源核实。"
            }}
          </p>
          <details>
            <summary>搜索摘要</summary>
            <p>{{ candidate.summary }}</p>
          </details>
        </article></el-collapse-item
      ></el-collapse
    >
    <p v-if="progress.data.value?.status === 'partial'" class="muted">
      部分来源或整理步骤未完成，已获得的信息会保留，可按需重新整理。
    </p>
  </section>
  <el-drawer v-model="advanced" title="高级搜索条件" size="min(100%, 640px)">
    <el-collapse model-value="advanced" class="discovery-advanced"
      ><el-collapse-item title="手动设置城市、天数和搜索范围" name="advanced"
        ><el-form label-position="top"
          ><div class="grid">
            <el-form-item label="岗位 / 技能关键词"
              ><el-input
                v-model="draft.keywords"
                aria-label="搜索关键词" /></el-form-item
            ><el-form-item label="城市（输入后回车）"
              ><el-select
                v-model="draft.cities"
                multiple
                filterable
                allow-create
                default-first-option /></el-form-item
            ><el-form-item label="每周可到岗天数"
              ><el-input-number
                v-model="draft.days_per_week"
                :min="1"
                :max="7" /></el-form-item
            ><el-form-item label="搜索范围（最多6组查询）"
              ><el-input-number v-model="draft.max_queries" :min="1" :max="6"
            /></el-form-item>
          </div>
          <el-checkbox v-model="draft.confirmed" aria-label="确认搜索条件"
            >确认以上搜索范围</el-checkbox
          ><el-button
            type="primary"
            :loading="busy"
            :disabled="
              !draft.confirmed || !draft.keywords || !publicConsent || running
            "
            @click="search()"
            >保存条件并搜索</el-button
          ></el-form
        ></el-collapse-item
      ></el-collapse
    >
  </el-drawer>
  <section class="panel discovery-history">
    <h2>最近保存的搜索条件</h2>
    <p v-if="!specs.data.value?.items.length" class="muted">
      搜索后会自动保存条件，方便下次继续找。
    </p>
    <p v-for="spec in specs.data.value?.items.slice(0, 8)" :key="spec.id">
      {{ spec.keywords }}
      <span class="muted">{{ spec.data.cities?.join(" / ") }}</span
      ><el-button
        link
        :disabled="!spec.confirmed || !publicConsent || running"
        @click="search(spec.id)"
        >再次找岗</el-button
      >
    </p>
  </section>
  <el-dialog v-model="intent.open" title="保存申请意向" width="560px"
    ><p class="muted">
      这会创建一份意向档案。请先核实信息，实际投递由你在原站完成。
    </p>
    <el-form label-position="top"
      ><el-form-item label="岗位名称"
        ><el-input v-model="intent.title" /></el-form-item
      ><el-form-item label="公司名称（请核实）"
        ><el-input v-model="intent.company" /></el-form-item
      ><el-button
        type="primary"
        :disabled="!intent.title.trim() || !intent.company.trim()"
        :loading="busy"
        @click="saveIntent"
        >保存意向档案</el-button
      ></el-form
    ></el-dialog
  >
</template>
