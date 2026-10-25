<script setup lang="ts">
import { ref } from "vue";
import { client, unwrap } from "../api/client";
import { useAction } from "../app/action";
const props = defineProps<{
    kind: "job" | "question" | "application" | "other";
    id?: string;
  }>(),
  { busy, error, act } = useAction(),
  message = ref(""),
  excerpt = ref(""),
  share = ref(false),
  saved = ref(false);
async function submit() {
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/feedback-reports", {
        body: {
          target_kind: props.kind,
          target_id: props.id ?? null,
          message: message.value,
          shared_excerpt: excerpt.value,
          share_confirmed: share.value,
        },
      }),
    );
    saved.value = true;
    message.value = "";
    excerpt.value = "";
  });
}
</script>
<template>
  <el-collapse
    ><el-collapse-item title="纠错 / 风险举报"
      ><el-form label-position="top"
        ><el-form-item label="问题和依据"
          ><el-input v-model="message" type="textarea" /></el-form-item
        ><el-form-item label="主动分享给运营的片段（可空）"
          ><el-input v-model="excerpt" type="textarea" /></el-form-item
        ><el-checkbox v-if="excerpt" v-model="share"
          >确认主动分享以上片段</el-checkbox
        ><el-alert v-if="error" :title="error" type="error" /><el-alert
          v-if="saved"
          title="报告已保存，等待处理"
          type="success"
        />
        <p>
          <el-button
            :loading="busy"
            :disabled="!message || (!!excerpt && !share)"
            @click="submit"
            >提交报告</el-button
          >
        </p></el-form
      ></el-collapse-item
    ></el-collapse
  >
</template>
