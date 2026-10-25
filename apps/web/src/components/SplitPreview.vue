<script setup lang="ts">
import { useWide } from "../app/navigation";
defineProps<{ selected: boolean; title?: string }>();
defineEmits<{ close: [] }>();
const wide = useWide();
</script>
<template>
  <div class="split-workspace" :class="{ 'is-single': !wide }">
    <div class="split-list"><slot /></div>
    <section v-if="wide" class="split-preview" aria-label="岗位速览">
      <template v-if="selected"><slot name="preview" /></template>
      <div v-else class="preview-placeholder">
        <span class="eyebrow">岗位速览</span>
        <h2>选择一份值得了解的机会</h2>
        <p>在列表中打开预览，阅读要求、来源和准备方向。</p>
      </div>
    </section>
  </div>
  <el-drawer
    :model-value="selected && !wide"
    :title="title || '岗位速览'"
    size="min(100%, 640px)"
    destroy-on-close
    @update:model-value="!$event && !wide && $emit('close')"
    ><slot name="preview"
  /></el-drawer>
</template>
