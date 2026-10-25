import { ref } from "vue";
export function useAction() {
  const busy = ref(false),
    error = ref("");
  async function act<T>(fn: () => Promise<T>): Promise<T | undefined> {
    if (busy.value) {
      error.value = "上一个操作仍在处理中，请稍后重试";
      return;
    }
    busy.value = true;
    error.value = "";
    try {
      return await fn();
    } catch (e) {
      error.value = e instanceof Error ? e.message : "操作失败";
    } finally {
      busy.value = false;
    }
  }
  return { busy, error, act };
}
