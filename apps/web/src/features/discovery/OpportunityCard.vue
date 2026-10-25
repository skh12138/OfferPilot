<script setup lang="ts">
import { difficultyLabels, type DiscoveryCard } from "./useDiscovery";
defineProps<{ item: DiscoveryCard }>();
defineEmits<{ save: [card: DiscoveryCard] }>();
function domain(url: string) {
  return new URL(url).hostname;
}
</script>
<template>
  <article
    class="opportunity-card"
    :aria-label="`招聘机会：${item.opportunity.title}`"
  >
    <div class="opportunity-heading">
      <div>
        <p class="opportunity-company">
          {{ item.opportunity.company || "公司待核实" }}
        </p>
        <h2>{{ item.opportunity.title }}</h2>
      </div>
      <el-tag
        :type="
          item.candidate.intelligence?.basis === 'job_text'
            ? 'success'
            : 'warning'
        "
        >{{
          item.candidate.intelligence?.basis === "job_text"
            ? "已读取职位正文"
            : "摘要整理 · 详情待核实"
        }}</el-tag
      >
    </div>
    <div class="opportunity-tags">
      <span>{{ item.opportunity.cities?.join(" / ") || "地点待核实" }}</span
      ><span>{{ item.opportunity.salary || "薪资未说明" }}</span
      ><span>{{ item.opportunity.education || "学历未说明" }}</span
      ><span v-if="item.opportunity.attendance">{{
        item.opportunity.attendance
      }}</span>
    </div>
    <div class="opportunity-content">
      <div>
        <h3>岗位要求</h3>
        <ul v-if="item.opportunity.requirements?.length">
          <li
            v-for="requirement in item.opportunity.requirements"
            :key="requirement"
          >
            {{ requirement }}
          </li>
        </ul>
        <p v-else class="muted">来源没有提供明确要求，需要到原站核实。</p>
        <template v-if="item.opportunity.responsibilities?.length"
          ><h3>主要工作</h3>
          <ul>
            <li v-for="task in item.opportunity.responsibilities" :key="task">
              {{ task }}
            </li>
          </ul></template
        >
        <p v-if="item.opportunity.deadline" class="muted">
          来源提及期限：{{ item.opportunity.deadline }}
        </p>
      </div>
      <section class="difficulty-box">
        <div class="difficulty-heading">
          <span>AI 预测难度</span
          ><strong>{{
            difficultyLabels[item.opportunity.difficulty?.level ?? "unknown"]
          }}</strong>
        </div>
        <p>{{ item.opportunity.difficulty?.reason }}</p>
        <template v-if="item.opportunity.difficulty?.preparation?.length"
          ><h4>建议准备</h4>
          <ul>
            <li
              v-for="advice in item.opportunity.difficulty.preparation"
              :key="advice"
            >
              {{ advice }}
            </li>
          </ul></template
        ><small>仅依据现有信息粗略预测，不代表企业面试标准或录用概率。</small>
      </section>
    </div>
    <p v-if="item.opportunity.relevance_reason" class="opportunity-reason">
      为什么推荐：{{ item.opportunity.relevance_reason }}
    </p>
    <div class="opportunity-footer">
      <div class="opportunity-sources">
        <a :href="item.candidate.url" target="_blank" rel="noopener noreferrer"
          >{{ domain(item.candidate.url) }} · 原始来源 ↗</a
        >
        <details v-if="item.sources.length > 1">
          <summary>另有 {{ item.sources.length - 1 }} 个来源</summary>
          <p
            v-for="source in item.sources.filter(
              (s) => s.id !== item.candidate.id,
            )"
            :key="source.id"
          >
            <a :href="source.url" target="_blank" rel="noopener noreferrer"
              >{{ domain(source.url) }} ↗</a
            >
          </p>
        </details>
      </div>
      <div class="toolbar">
        <RouterLink
          v-if="item.candidate.job_id"
          :to="`/jobs/${item.candidate.job_id}`"
          >查看岗位与证据 →</RouterLink
        ><el-button type="primary" plain @click="$emit('save', item)"
          >保存申请意向</el-button
        >
      </div>
    </div>
    <details class="source-excerpt">
      <summary>查看整理依据与信息边界</summary>
      <p>
        字段来自{{
          item.candidate.intelligence?.basis === "job_text"
            ? "已读取的职位文本"
            : "搜索标题和摘要"
        }}，缺失信息不会自动补成事实。招聘状态仍需原站确认。
      </p>
      <blockquote>{{ item.candidate.summary }}</blockquote>
    </details>
  </article>
</template>
