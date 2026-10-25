import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useSession } from "../src/app/session";
import { useDraft, useUi } from "../src/app/ui";
import { nextTick, watchEffect } from "vue";
import { formatDate } from "../src/utils/dates";

beforeEach(() => {
  setActivePinia(createPinia());
  useSession().user = {
    id: "alpha",
    username: "alpha",
    is_admin: false,
    timezone: "Asia/Shanghai",
  };
});
describe("session-only editable drafts", () => {
  it("updates reactive text on the first unsaved input", async () => {
    const form = useDraft("first-input", () => ({ text: "" }));
    let observed = "";
    const stop = watchEffect(() => {
      observed = form.draft.value.text;
    });
    form.draft.value.text = "新输入";
    await nextTick();
    expect(observed).toBe("新输入");
    stop();
  });
  it("keeps dirty fields through remote refresh and resumes the same entity", () => {
    const form = useDraft("profile-edit", () => ({ text: "" }));
    form.load({ text: "server" });
    form.draft.value.text = "unsaved";
    form.load({ text: "new server" });
    expect(form.draft.value.text).toBe("unsaved");
    expect(form.dirty.value).toBe(true);
    expect(
      useDraft("profile-edit", () => ({ text: "" })).draft.value.text,
    ).toBe("unsaved");
    form.reset();
    expect(form.draft.value.text).toBe("server");
    form.load({ text: "latest" });
    expect(form.draft.value.text).toBe("latest");
  });
  it("isolates answers by version, question and user and clears on logout", () => {
    const a = useDraft("question:v1:a", () => ({ text: "" })),
      b = useDraft("question:v1:b", () => ({ text: "" }));
    a.draft.value.text = "answer A";
    b.draft.value.text = "answer B";
    expect(a.draft.value.text).toBe("answer A");
    expect(
      useDraft("question:v2:a", () => ({ text: "" })).draft.value.text,
    ).toBe("");
    useSession().user = {
      id: "beta",
      username: "beta",
      is_admin: false,
      timezone: "Asia/Shanghai",
    };
    expect(a.draft.value.text).toBe("");
    useUi().clear();
    expect(Object.keys(useUi().drafts)).toHaveLength(0);
    expect(localStorage.length).toBe(0);
  });
  it("clears personal derived drafts on confirmed deletion and retains unrelated task input", () => {
    const profile = useDraft("profile-edit", () => ({ text: "" })),
      task = useDraft("task-create", () => ({ title: "" }));
    profile.draft.value.text = "personal";
    task.draft.value.title = "ordinary task";
    useUi().clearPersonal();
    expect(profile.draft.value.text).toBe("");
    expect(task.draft.value.title).toBe("ordinary task");
  });
  it("formats date-only values without UTC conversion and instants in Shanghai", () => {
    expect(formatDate("2026-10-24")).toBe("2026年10月24日");
    expect(formatDate("2026-10-23T18:30:00Z")).toContain("24");
    expect(formatDate("2026-10-23T18:30:00Z")).toContain("02:30");
  });
});
