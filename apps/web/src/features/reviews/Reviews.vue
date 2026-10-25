<script setup lang="ts">
import DraftDrawer from "../../components/DraftDrawer.vue";
import AsyncState from "../../components/AsyncState.vue";
import { useDraft } from "../../app/ui";
import { useChoiceQuery } from "../../app/navigation";
import { formatDate } from "../../utils/dates";
import { reactive, ref } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { client, unwrap, key } from "../../api/client";
import type { components } from "../../api/schema";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
const session = useSession(),
  cache = useQueryClient(),
  { busy, error, act } = useAction(),
  showOffer = ref(false),
  showReview = ref(false),
  selected = ref<string[]>([]),
  comparison = ref<components["schemas"]["OfferDTO"][]>([]);
const overview = useQuery({
  queryKey: ["overview", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/reports/overview")),
});
const offers = useQuery({
  queryKey: ["offers", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/offers")),
});
const apps = useQuery({
  queryKey: ["applications", session.user?.id],
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/applications", {
        params: { query: { limit: 100 } },
      }),
    ),
});
const reviews = useQuery({
  queryKey: ["interview-reviews", session.user?.id],
  queryFn: async () => unwrap(await client.GET("/api/v1/interview-reviews")),
});
const offerState = useDraft<components["schemas"]["OfferInput"]>(
  "offer-create",
  () => ({
    application_id: "",
    notification_confirmed: false,
    type: "oral",
    source: "本人记录的实际通知",
    salary_minimum: null,
    salary_maximum: null,
    currency: "CNY",
    salary_unit: "unknown",
    salary_raw: "",
    terms: { notes: "" },
    reply_deadline: null,
  }),
);
const offer = reactive(offerState.draft.value);
const tab = useChoiceQuery("tab", ["reviews", "offers"], "reviews");
const salaryUnits: Record<string, string> = {
  day: "天",
  month: "月",
  year: "年",
  hour: "小时",
  unknown: "口径未说明",
};
const offerDecisions: Record<string, string> = {
  undecided: "尚未决定",
  withdrawn: "已撤回",
  recorded: "已记录通知",
  notified: "已记录通知",
  negotiating: "沟通中",
  accepted: "本人已接受",
  declined: "本人已拒绝",
  expired: "本人确认已失效",
};
const reviewState = useDraft<components["schemas"]["InterviewReviewInput"]>(
  "review-create",
  () => ({
    application_id: "",
    round_id: null,
    questions_asked: "",
    user_answers_summary: "",
    explicit_feedback: "",
    user_inference: "",
    next_steps: "",
  }),
);
const review = reactive(reviewState.draft.value);
async function saveOffer() {
  await act(async () => {
    unwrap(await client.POST("/api/v1/offers", { body: offer }));
    offerState.saved();
    showOffer.value = false;
    await refreshOfferViews();
  });
}
async function saveReview() {
  await act(async () => {
    unwrap(await client.POST("/api/v1/interview-reviews", { body: review }));
    reviewState.saved();
    showReview.value = false;
    await reviews.refetch();
  });
}
async function decide(
  row: components["schemas"]["OfferDTO"],
  decision: components["schemas"]["OfferEventInput"]["decision"],
) {
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/offers/{offer_id}/events", {
        params: { path: { offer_id: row.id } },
        headers: key(),
        body: {
          expected_revision: row.revision,
          decision,
          reason: "本人主动记录决定",
          user_confirmed: true,
        },
      }),
    );
    await refreshOfferViews();
  });
}
async function compare() {
  await act(async () => {
    comparison.value = unwrap(
      await client.POST("/api/v1/offers/compare", {
        body: { ids: selected.value },
      }),
    );
  });
}
async function refreshOfferViews() {
  await cache.invalidateQueries({
    predicate: (q) =>
      [
        "offers",
        "overview",
        "applications",
        "application",
        "today",
        "tasks",
      ].includes(String(q.queryKey[0])),
  });
}
</script>
<template>
  <h1>复盘与选择</h1>
  <p class="subtitle">把实际反馈留下，把推测单独写清，再决定下一步。</p>
  <el-alert
    v-if="error && !showOffer && !showReview"
    :title="error"
    type="error"
  />
  <AsyncState
    :pending="
      overview.isPending.value ||
      offers.isPending.value ||
      reviews.isPending.value ||
      apps.isPending.value
    "
    :error="
      overview.error.value ||
      offers.error.value ||
      reviews.error.value ||
      apps.error.value
    "
    @retry="
      overview.refetch();
      offers.refetch();
      reviews.refetch();
      apps.refetch();
    "
  />
  <div class="metrics">
    <div class="metric">
      申请样本<strong>{{ overview.data.value?.sample_size ?? "—" }}</strong>
    </div>
    <div class="metric">
      实际投递记录<strong>{{
        overview.data.value?.actual_submissions ?? "—"
      }}</strong>
    </div>
    <div class="metric">
      等待 / 未知<strong>{{
        overview.data.value?.waiting_or_unknown ?? "—"
      }}</strong>
    </div>
    <div class="metric">
      Offer 记录<strong>{{ offers.data.value?.items.length ?? "—" }}</strong>
    </div>
  </div>
  <p class="muted">
    {{ overview.data.value?.note }} · 统计截至
    {{ formatDate(overview.data.value?.to_date) }}
  </p>
  <el-tabs v-model="tab"
    ><el-tab-pane label="面试复盘" name="reviews">
      <section class="panel">
        <h2>面试复盘</h2>
        <el-button @click="showReview = true">记录一场复盘</el-button>
        <p
          v-if="
            !reviews.isPending.value &&
            !reviews.error.value &&
            !reviews.data.value?.items.length
          "
          class="empty"
        >
          尚无面试复盘，可在面试后记录实际问题与收到的反馈。
        </p>
        <article
          v-for="item in reviews.data.value?.items"
          :key="item.id"
          class="fact"
        >
          <h3>实际问题</h3>
          <p>{{ item.questions_asked }}</p>
          <h3>明确收到的反馈</h3>
          <p>{{ item.explicit_feedback || "没有记录明确反馈" }}</p>
          <h3>个人推测</h3>
          <p>{{ item.user_inference || "未填写" }}</p>
          <p>下一步：{{ item.next_steps }}</p>
          <RouterLink :to="'/applications/' + item.application_id"
            >回到申请准备下一轮 →</RouterLink
          >
        </article>
      </section> </el-tab-pane
    ><el-tab-pane label="Offer 记录与比较" name="offers">
      <section class="panel">
        <div class="toolbar">
          <h2 style="margin: 0">Offer 记录</h2>
          <el-button type="primary" @click="showOffer = true"
            >记录实际通知</el-button
          ><el-button
            :disabled="!selected.length || selected.length > 4"
            @click="compare"
            >比较 {{ selected.length }} / 4</el-button
          >
        </div>
        <div v-if="selected.length" class="selection-bar">
          <span>已选 {{ selected.length }} / 4</span
          ><el-tag
            v-for="id in selected"
            :key="id"
            closable
            @close="selected = selected.filter((v) => v !== id)"
            >通知 {{ id.slice(0, 8) }}</el-tag
          ><el-button text @click="selected = []">清空比较</el-button>
        </div>
        <p class="muted">
          口头意向与书面通知分开；期限经过只提示到期，不自动判定失效。接受一份不会关闭其他机会。
        </p>
        <article
          v-for="item in offers.data.value?.items"
          :key="item.id"
          class="fact"
        >
          <el-checkbox
            v-model="selected"
            :value="item.id"
            :disabled="selected.length >= 4 && !selected.includes(item.id)"
            >加入比较</el-checkbox
          >
          <h3>
            {{
              apps.data.value?.items.find((a) => a.id === item.application_id)
                ?.company
            }}
            · {{ item.type === "oral" ? "口头意向" : "书面通知" }}
          </h3>
          <div class="tags">
            <el-tag>{{ offerDecisions[item.decision] ?? item.decision }}</el-tag
            ><el-tag
              v-if="
                item.reply_deadline &&
                item.reply_deadline < new Date().toLocaleDateString('en-CA')
              "
              type="warning"
              >回复期限已过，请核实</el-tag
            >
          </div>
          <p>
            {{ item.salary_raw || "薪资待确认" }} · {{ item.currency }} /
            {{ salaryUnits[item.salary_unit] ?? item.salary_unit }}
          </p>
          <p>
            回复期限：{{
              item.reply_deadline ? formatDate(item.reply_deadline) : "未说明"
            }}
            · 来源：{{ item.source }}
          </p>
          <div class="toolbar">
            <el-button @click="decide(item, 'negotiating')"
              >记录沟通中</el-button
            ><el-button type="primary" @click="decide(item, 'accepted')"
              >本人决定接受</el-button
            ><el-button @click="decide(item, 'declined')"
              >本人决定拒绝</el-button
            ><el-button link @click="decide(item, 'expired')"
              >本人确认已失效</el-button
            >
          </div>
        </article>
        <p
          v-if="
            !offers.isPending.value &&
            !offers.error.value &&
            !offers.data.value?.items.length
          "
          class="empty"
        >
          尚无实际 Offer 通知
        </p>
      </section>
      <section v-if="comparison.length" class="panel">
        <h2>并排比较，不做薪资口径换算</h2>
        <p class="scroll-hint">左右滚动查看原始字段，薪资不进行口径换算。</p>
        <div class="local-scroll" tabindex="0">
          <el-table class="comparison-table" :data="comparison"
            ><el-table-column label="性质"
              ><template #default="scope">{{
                scope.row.type === "oral" ? "口头意向" : "书面通知"
              }}</template></el-table-column
            ><el-table-column label="原始薪资"
              ><template #default="scope">{{
                scope.row.salary_raw || "未提供"
              }}</template></el-table-column
            ><el-table-column label="单位"
              ><template #default="scope">{{
                salaryUnits[scope.row.salary_unit] ?? scope.row.salary_unit
              }}</template></el-table-column
            ><el-table-column label="币种"
              ><template #default="scope">{{
                scope.row.currency || "未提供"
              }}</template></el-table-column
            ><el-table-column label="回复期限"
              ><template #default="scope">{{
                scope.row.reply_deadline
                  ? formatDate(scope.row.reply_deadline)
                  : "未提供"
              }}</template></el-table-column
            ><el-table-column label="城市"
              ><template #default="scope">{{
                scope.row.terms.city || "未提供"
              }}</template></el-table-column
            ><el-table-column label="带教"
              ><template #default="scope">{{
                scope.row.terms.mentoring || "未提供"
              }}</template></el-table-column
            ></el-table
          >
        </div>
      </section>
    </el-tab-pane></el-tabs
  >
  <DraftDrawer
    v-model="showOffer"
    title="记录实际 Offer 通知"
    :dirty="offerState.dirty.value"
    :busy="busy"
    ><el-alert v-if="error" :title="error" type="error" /><el-form
      label-position="top"
      ><el-form-item label="对应申请"
        ><el-select v-model="offer.application_id" aria-label="Offer 对应申请"
          ><el-option
            v-for="app in apps.data.value?.items"
            :key="app.id"
            :value="app.id"
            :label="
              app.company + ' · ' + app.title
            " /></el-select></el-form-item
      ><el-form-item label="通知性质"
        ><el-radio-group v-model="offer.type"
          ><el-radio value="oral">口头意向</el-radio
          ><el-radio value="written">书面通知</el-radio></el-radio-group
        ></el-form-item
      ><el-form-item label="待遇原文"
        ><el-input
          v-model="offer.salary_raw"
          aria-label="薪资原文" /></el-form-item
      ><el-form-item label="薪资口径"
        ><el-select v-model="offer.salary_unit"
          ><el-option
            v-for="value in ['unknown', 'day', 'month', 'year', 'hour']"
            :key="value"
            :value="value" /></el-select></el-form-item
      ><el-form-item label="城市"
        ><el-input v-model="offer.terms.city" /></el-form-item
      ><el-form-item label="回复截止日期"
        ><el-date-picker
          v-model="offer.reply_deadline"
          value-format="YYYY-MM-DD" /></el-form-item
      ><el-checkbox v-model="offer.notification_confirmed"
        >本人确认已收到实际通知</el-checkbox
      >
      <p>
        <el-button
          type="primary"
          :loading="busy"
          :disabled="!offer.notification_confirmed || !offer.application_id"
          @click="saveOffer"
          >保存 Offer 记录</el-button
        >
      </p></el-form
    ></DraftDrawer
  >
  <DraftDrawer
    v-model="showReview"
    title="面试复盘"
    :dirty="reviewState.dirty.value"
    :busy="busy"
    ><el-alert v-if="error" :title="error" type="error" /><el-form
      label-position="top"
      ><el-form-item label="对应申请"
        ><el-select v-model="review.application_id"
          ><el-option
            v-for="app in apps.data.value?.items"
            :key="app.id"
            :value="app.id"
            :label="
              app.company + ' · ' + app.title
            " /></el-select></el-form-item
      ><el-form-item label="实际被问到的问题"
        ><el-input
          v-model="review.questions_asked"
          type="textarea" /></el-form-item
      ><el-form-item label="我的回答摘要"
        ><el-input
          v-model="review.user_answers_summary"
          type="textarea" /></el-form-item
      ><el-form-item label="明确收到的反馈"
        ><el-input
          v-model="review.explicit_feedback"
          type="textarea" /></el-form-item
      ><el-form-item label="个人推测（不作为招聘结论）"
        ><el-input
          v-model="review.user_inference"
          type="textarea" /></el-form-item
      ><el-form-item label="下一步"
        ><el-input v-model="review.next_steps" type="textarea" /></el-form-item
      ><el-button
        type="primary"
        :loading="busy"
        :disabled="!review.application_id"
        @click="saveReview"
        >保存复盘</el-button
      ></el-form
    ></DraftDrawer
  >
</template>
