<script setup lang="ts">
import { difficultyLabels, type DiscoveryCard } from "./useDiscovery";
defineProps<{ item: DiscoveryCard; selected: boolean }>();
defineEmits<{ preview: [item: DiscoveryCard] }>();
</script>
<template>
  <article
    class="flat-row opportunity-row"
    :class="{ 'is-selected': selected }"
    :aria-label="`招聘机会：${item.opportunity.title}`"
  >
    <div class="row-top">
      <span class="eyebrow">{{
        item.opportunity.company || "公司待核实"
      }}</span>
      <div class="row-actions">
        <span class="row-status"
          >{{
            item.candidate.intelligence?.basis === "job_text"
              ? "正文已读取"
              : "摘要待核实"
          }}<span v-if="selected"> · 已选中</span></span
        ><el-button
          text
          :aria-label="`预览${item.opportunity.title}`"
          :aria-pressed="selected"
          @click="$emit('preview', item)"
          >预览 →</el-button
        >
      </div>
    </div>
    <h2>
      <RouterLink
        v-if="item.candidate.job_id"
        :to="`/jobs/${item.candidate.job_id}`"
        >{{ item.opportunity.title }}</RouterLink
      ><span v-else>{{ item.opportunity.title }}</span>
    </h2>
    <div class="row-meta">
      <span>{{ item.opportunity.cities?.join(" / ") || "地点待核实" }}</span
      ><span>{{ item.opportunity.salary || "薪资未提供" }}</span
      ><span>{{
        item.opportunity.attendance ||
        item.opportunity.education ||
        "要求待核实"
      }}</span
      ><span
        >AI 预测 ·
        {{
          difficultyLabels[item.opportunity.difficulty?.level ?? "unknown"]
        }}</span
      >
    </div>
    <p class="row-summary">
      {{
        item.opportunity.requirements?.slice(0, 2).join(" · ") ||
        "详细要求待核实，可预览已有信息与来源"
      }}
    </p>
  </article>
</template>
