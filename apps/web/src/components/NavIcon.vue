<script setup lang="ts">
defineProps<{ name: string }>();
const paths: Record<string, string> = {
  today: "m3 10 9-7 9 7v11h-7v-7h-4v7H3z",
  discover: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  jobs: "M3 7h18v14H3zM8 7V3h8v4M3 12h18",
  applications: "M6 3h12v18H6zM9 8h6M9 12h6M9 16h4",
  study: "M4 5h16v16H4zM8 2v6M16 2v6M4 10h16",
  profile: "M20 21v-3a8 5 0 0 0-16 0v3M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  reviews: "M4 21V11h4v10M10 21V3h4v18M16 21V7h4v14",
  operations: "M4 4h16v16H4zM8 8h8M8 12h8M8 16h4",
  menu: "M3 6h18M3 12h18M3 18h18",
};
</script>
<template>
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.jobs" />
  </svg>
</template>
