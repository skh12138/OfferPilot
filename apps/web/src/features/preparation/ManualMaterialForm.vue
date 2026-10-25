<script setup lang="ts">
import { useDraft } from "../../app/ui";
import { reactive } from "vue";
import { client, unwrap } from "../../api/client";
import { useAction } from "../../app/action";
const props = defineProps<{ applicationId: string; revision: number }>(),
  emit = defineEmits<{ saved: [] }>(),
  { busy, error, act } = useAction();
const form = useDraft(
  () => `manual-material:${props.applicationId}`,
  () => ({
    title: "",
    deliverable: "",
    acceptance: "",
    introduction: "",
    contact: "",
  }),
);
const draft = reactive(form.draft.value);
async function save() {
  await act(async () => {
    unwrap(
      await client.POST("/api/v1/applications/{app_id}/preparation-bundles", {
        params: { path: { app_id: props.applicationId } },
        body: {
          expected_revision: props.revision,
          reason: "本人手工编写材料",
          data: {
            claims: [],
            gaps: [],
            tasks: draft.title
              ? [
                  {
                    title: draft.title,
                    reason: "本人选择",
                    deliverable: draft.deliverable,
                    acceptance: draft.acceptance,
                    priority: "normal",
                    requirement_ids: [],
                    fact_ids: [],
                  },
                ]
              : [],
            introduction: draft.introduction,
            contact_draft: draft.contact,
          },
        },
      }),
    );
    form.saved();
    emit("saved");
  });
}
</script>
<template>
  <el-collapse class="panel"
    ><el-collapse-item title="手工编写材料（模型不可用时也可使用）"
      ><el-form label-position="top"
        ><el-form-item label="自我介绍组织提纲（本人经历请引用已确认事实）"
          ><el-input
            v-model="draft.introduction"
            type="textarea" /></el-form-item
        ><el-form-item label="联系草稿"
          ><el-input v-model="draft.contact" type="textarea" /></el-form-item
        ><el-form-item label="准备任务（可空）"
          ><el-input v-model="draft.title" /></el-form-item
        ><el-form-item label="交付物"
          ><el-input v-model="draft.deliverable" /></el-form-item
        ><el-form-item label="验收标准"
          ><el-input v-model="draft.acceptance" /></el-form-item
        ><el-alert v-if="error" type="error" :title="error" /><el-button
          :loading="busy"
          @click="save"
          >保存人工材料草稿，随后审核</el-button
        ></el-form
      ></el-collapse-item
    ></el-collapse
  >
</template>
