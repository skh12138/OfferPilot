import { defineStore } from "pinia";
import { computed, reactive, toValue, type MaybeRefOrGetter } from "vue";
import { useSession } from "./session";
import { clone } from "../api/clone";

interface DraftEntry {
  value: unknown;
  baseline: string;
}
export const useUi = defineStore("ui", () => {
  const drafts = reactive<Record<string, DraftEntry>>({});
  const positions = new Map<string, number>();
  const lists = reactive<Record<string, string>>({});
  const returns = reactive<Record<string, string>>({});
  const dirty = computed(() =>
    Object.values(drafts).some((e) => JSON.stringify(e.value) !== e.baseline),
  );
  function clearPersonal() {
    for (const key of Object.keys(drafts))
      if (
        /:(profile-edit|resume-import|question:|bundle:|manual-material:|study-editor:)/.test(
          key,
        )
      )
        delete drafts[key];
  }
  function clear() {
    for (const key of Object.keys(drafts)) delete drafts[key];
    positions.clear();
    for (const key of Object.keys(lists)) delete lists[key];
    for (const key of Object.keys(returns)) delete returns[key];
  }
  return { drafts, positions, lists, returns, dirty, clear, clearPersonal };
});

/** Only editable drafts live here. Remote snapshots remain in Vue Query. */
export function useDraft<T extends object>(
  name: MaybeRefOrGetter<string>,
  initial: () => T,
) {
  const ui = useUi(),
    session = useSession();
  const scope = computed(
    () => `${session.user?.id ?? "anonymous"}:${toValue(name)}`,
  );
  function entry() {
    if (!ui.drafts[scope.value]) {
      const value = initial();
      ui.drafts[scope.value] = { value, baseline: JSON.stringify(value) };
    }
    // Read through the reactive map even on first use; assignment returns a raw object.
    return ui.drafts[scope.value];
  }
  const draft = computed<T>({
    get: () => entry().value as T,
    set: (value) => {
      entry().value = value;
    },
  });
  const dirty = computed(
    () => JSON.stringify(draft.value) !== entry().baseline,
  );
  function saved() {
    entry().baseline = JSON.stringify(draft.value);
  }
  function load(value: T) {
    if (!dirty.value) {
      draft.value = clone(value);
      saved();
    }
  }
  function reset() {
    draft.value = JSON.parse(entry().baseline) as T;
  }
  return { draft, dirty, saved, load, reset };
}
