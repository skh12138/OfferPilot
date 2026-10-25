<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import { ref } from "vue";
const props = defineProps<{
  modelValue: boolean;
  title: string;
  dirty?: boolean;
  busy?: boolean;
}>();
defineEmits<{ "update:modelValue": [value: boolean] }>();
const confirming = ref(false);
async function close(done: () => void) {
  if (props.busy || confirming.value) return;
  confirming.value = true;
  if (props.dirty) {
    try {
      await ElMessageBox.confirm(
        "未提交内容会在本次登录会话保留；刷新或退出会丢失。",
        "保留草稿并关闭？",
        {
          confirmButtonText: "保留草稿并关闭",
          cancelButtonText: "继续编辑",
          type: "warning",
        },
      );
    } catch {
      confirming.value = false;
      return;
    }
  }
  done();
  confirming.value = false;
}
</script>
<template>
  <el-drawer
    :model-value="modelValue"
    :title="title"
    size="min(100%, 640px)"
    :before-close="close"
    @update:model-value="$emit('update:modelValue', $event)"
    ><p class="muted draft-note">
      未提交草稿仅在当前登录会话内保留，刷新后不能恢复。
    </p>
    <slot
  /></el-drawer>
</template>
