<script setup lang="ts">
import type { components } from "../../api/schema";
import { label, preferenceLabel } from "../../utils/labels";
import { formatDate } from "../../utils/dates";
function conditionText(value: unknown): string {
  if (value === null || value === undefined) return "未提供";
  if (Array.isArray(value))
    return value.map((v) => label(String(v))).join("、");
  if (typeof value === "object") return "字段格式待核实，请查看原文";
  return label(String(value));
}
defineProps<{ job: components["schemas"]["JobDTO"] }>();
</script>
<template>
  <div class="preview-content" v-if="job.current">
    <p class="eyebrow">{{ job.current.data.company || "公司待核实" }}</p>
    <h2>{{ job.current.data.title }}</h2>
    <div class="row-meta">
      <span>{{ job.current.data.cities?.join(" / ") || "地点待核实" }}</span
      ><span>{{ job.current.data.salary?.raw || "薪资未提供" }}</span
      ><span>个人意向：{{ preferenceLabel(job.preference) }}</span>
    </div>
    <div class="tags">
      <el-tag>{{ label(job.verification?.source_status || "unknown") }}</el-tag
      ><el-tag type="info">{{
        label(job.verification?.availability_status || "unknown")
      }}</el-tag
      ><el-tag type="warning">{{
        label(job.verification?.risk_status || "unknown")
      }}</el-tag>
    </div>
    <p class="muted">
      正文已读取不等于招聘真实有效，缺失条件仍需本人到来源核实。
    </p>
    <section class="preview-section">
      <h3>条件与资格</h3>
      <p>资格：{{ label(job.eligibility) }}</p>
      <dl class="definition-grid">
        <div
          v-for="(condition, name) in job.current.data.conditions"
          :key="name"
        >
          <dt>{{ label(name) }}</dt>
          <dd>
            {{
              condition.unrestricted
                ? "明确不限"
                : conditionText(condition.value)
            }}
            · {{ label(condition.strength ?? "hard") }} ·
            {{ label(condition.review_status ?? "missing") }}
          </dd>
        </div>
      </dl>
      <p class="muted">
        缺失：{{
          job.current.data.missing_fields?.map(label).join("、") ||
          "请查看原文证据"
        }}
      </p>
    </section>
    <section class="preview-section">
      <h3>岗位要求与职责</h3>
      <ul v-if="job.current.data.requirements?.length">
        <li
          v-for="item in job.current.data.requirements"
          :key="item.requirement_id"
        >
          {{ item.text }}
        </li>
      </ul>
      <p v-else class="muted">未提供明确要求</p>
    </section>
    <section class="preview-section">
      <h3>来源与原文证据</h3>
      <p v-for="source in job.sources" :key="source.id">
        <a
          :href="source.canonical_url"
          target="_blank"
          rel="noopener noreferrer"
          >打开 {{ source.board }} 原站 ↗</a
        ><span v-for="alias in source.aliases" :key="alias">
          ·
          <a :href="alias" target="_blank" rel="noopener noreferrer"
            >其他已发现入口 ↗</a
          ></span
        >
      </p>
      <el-collapse
        ><el-collapse-item
          v-for="snapshot in job.snapshots"
          :key="snapshot.id"
          :title="
            snapshot.kind === 'provider_extracted'
              ? '提供商提取文本快照'
              : '用户提供文本'
          "
          ><div
            class="evidence"
            v-for="(paragraph, name) in snapshot.paragraphs"
            :key="name"
          >
            {{ name }} · {{ paragraph }}
          </div></el-collapse-item
        ><el-collapse-item title="历史版本"
          ><p v-for="version in job.versions" :key="version.id">
            {{ formatDate(version.created_at) }} · {{ version.reason }}
          </p></el-collapse-item
        ></el-collapse
      >
    </section>
    <p v-for="reason in job.ranking_reasons" :key="reason" class="muted">
      {{ reason.replace(job.preference, preferenceLabel(job.preference)) }}
    </p>
  </div>
</template>
