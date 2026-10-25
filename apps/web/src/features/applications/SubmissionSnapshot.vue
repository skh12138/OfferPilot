<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import { client, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import { useSession } from "../../app/session";
const props = defineProps<{
    submission: components["schemas"]["SubmissionDTO"];
    profiles: components["schemas"]["ProfileDTO"][];
  }>(),
  session = useSession();
const resume = useQuery({
  queryKey: ["resume", session.user?.id, props.submission.resume_version_id],
  enabled: !!props.submission.resume_version_id,
  queryFn: async () =>
    unwrap(
      await client.GET("/api/v1/resume-versions/{resume_id}", {
        params: {
          path: { resume_id: props.submission.resume_version_id ?? "" },
        },
      }),
    ),
});
</script>
<template>
  <el-collapse
    ><el-collapse-item
      :title="submission.submitted_at + ' · ' + submission.channel"
      ><p>
        {{
          submission.missing_materials
            ? "历史材料不完整 / 待补录"
            : "已锁定实际提交的资料版本"
        }}
      </p>
      <p v-if="resume.data.value?.deleted_at">当时材料已删除</p>
      <pre v-else-if="resume.data.value?.text" class="evidence">{{
        resume.data.value.text
      }}</pre>
      <p v-else class="muted">没有保存当时的简历正文</p>
      <div
        v-for="profile in profiles.filter(
          (v) => v.id === submission.profile_version_id,
        )"
        :key="profile.id"
      >
        <p>{{ profile.unavailable ? "资料已删除" : profile.reason }}</p>
        <p
          v-for="fact in profile.unavailable ? [] : profile.facts"
          :key="fact.fact_id"
        >
          {{ fact.text }} · {{ fact.status }}
        </p>
      </div>
      <p class="muted">最新版资料不会替换此处的历史快照。</p></el-collapse-item
    ></el-collapse
  >
</template>
