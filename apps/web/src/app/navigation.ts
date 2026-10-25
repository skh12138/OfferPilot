import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type Ref,
} from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { useUi } from "./ui";
import { useSession } from "./session";

export function useChoiceQuery<T extends string>(
  name: string,
  choices: readonly T[],
  fallback: T,
) {
  const route = useRoute(),
    router = useRouter();
  return computed<T>({
    get: () => choices.find((v) => v === route.query[name]) ?? fallback,
    set: (value) => {
      void router.replace({
        query: {
          ...route.query,
          [name]: value === fallback ? undefined : value,
        },
      });
    },
  });
}
export function useTextQuery(name = "q") {
  const route = useRoute(),
    router = useRouter();
  const input = ref(String(route.query[name] ?? "")),
    composing = ref(false);
  let timer: ReturnType<typeof setTimeout> | undefined;
  function schedule() {
    clearTimeout(timer);
    if (!composing.value)
      timer = setTimeout(() => {
        void router.replace({
          query: {
            ...route.query,
            [name]: input.value || undefined,
            cursor: undefined,
            selected: undefined,
          },
        });
      }, 280);
  }
  watch(input, schedule);
  watch(
    () => route.query[name],
    (value) => {
      const next = String(value ?? "");
      if (next !== input.value) {
        clearTimeout(timer);
        input.value = next;
      }
    },
  );
  function compositionStart() {
    composing.value = true;
    clearTimeout(timer);
  }
  function compositionEnd() {
    composing.value = false;
    schedule();
  }
  onBeforeUnmount(() => clearTimeout(timer));
  return { input, compositionStart, compositionEnd, composing };
}
export function useWide() {
  const wide = ref(false);
  let media: MediaQueryList | undefined;
  let observer: ResizeObserver | undefined;
  function update() {
    const main = document.querySelector<HTMLElement>(".app-main");
    wide.value = !!media?.matches && (!main || main.clientWidth >= 850);
  }
  onMounted(() => {
    media = window.matchMedia("(min-width: 1280px)");
    update();
    media.addEventListener("change", update);
    const main = document.querySelector(".app-main");
    if (main && typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(update);
      observer.observe(main);
    }
  });
  onBeforeUnmount(() => {
    media?.removeEventListener("change", update);
    observer?.disconnect();
  });
  return wide;
}
export function useListPosition(ready: Ref<boolean>) {
  const route = useRoute(),
    ui = useUi(),
    session = useSession();
  const path = route.path,
    owner = session.user?.id;
  let restored = false;
  watch(
    ready,
    async (value) => {
      if (!value || restored) return;
      restored = true;
      await nextTick();
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          const top = ui.positions.get(`${owner}:${route.fullPath}`);
          if (top !== undefined) window.scrollTo(0, top);
        }),
      );
    },
    { immediate: true },
  );
  onBeforeRouteLeave((to) => {
    ui.positions.set(`${owner}:${route.fullPath}`, window.scrollY);
    ui.lists[path] = route.fullPath;
    if (to.path.startsWith("/jobs/") && ["/discover", "/jobs"].includes(path))
      ui.returns.jobs = route.fullPath;
  });
}
