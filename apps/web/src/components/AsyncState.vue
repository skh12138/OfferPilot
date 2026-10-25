<script setup lang="ts">
defineProps<{
  pending?: boolean;
  error?: unknown;
  empty?: boolean;
  message?: string;
}>();
defineEmits<{ retry: [] }>();
</script>
<template>
  <div v-if="pending" class="loading-state" role="status">
    <el-skeleton :rows="3" animated /><span class="sr-only">正在加载</span>
  </div>
  <div v-else-if="error" class="state-box" role="alert">
    <h3>暂时无法加载</h3>
    <p>{{ message || "请检查连接后重试，已保存的内容不会丢失。" }}</p>
    <el-button @click="$emit('retry')">重新加载</el-button>
  </div>
  <div v-else-if="empty" class="state-box">
    <h3>{{ message || "还没有记录" }}</h3>
    <slot />
  </div>
</template>
