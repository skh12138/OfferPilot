import { clone } from "../../api/clone";
import { useDraft } from "../../app/ui";
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { client, unwrap, key } from "../../api/client";
import { useAction } from "../../app/action";
import { useApplication } from "./useApplication";
import type { components } from "../../api/schema";

export function useApplicationActions() {
  const route = useRoute(),
    router = useRouter(),
    id = computed(() => String(route.params.id));
  const {
      app,
      rounds,
      events,
      submissions,
      bundles,
      profile,
      tasks,
      jobs,
      refresh,
    } = useApplication(id),
    { busy, error, act } = useAction();
  const runId = computed({
    get: () => String(route.query.run ?? ""),
    set: (run) => {
      void router.replace({ query: { ...route.query, run } });
    },
  });
  const basisJobId = ref<string | null>(null);
  const dialog = ref(""),
    profileId = ref<string | null>(null),
    missing = ref(true),
    confirmed = ref(false),
    submittedAt = ref(new Date().toISOString()),
    observed = ref(""),
    target = ref<components["schemas"]["EventInput"]["to_stage"]>("preparing"),
    eventType =
      ref<components["schemas"]["EventInput"]["event_type"]>("advance"),
    reason = ref(""),
    taskAction = ref<"keep" | "cancel" | "detach">("keep");
  const linkDraft = useDraft(
    () => `application-links:${id.value}`,
    () => ({
      fields: {
        job_url: "",
        apply_url: "",
        progress_url: "",
        navigation_hint: "",
      },
      revision: 0,
    }),
  );
  const links = reactive(linkDraft.draft.value.fields);
  watch(
    () => app.data.value,
    (row) => {
      if (row && !linkDraft.dirty.value) {
        links.job_url = row.job_url ?? "";
        links.apply_url = row.apply_url ?? "";
        links.progress_url = row.progress_url ?? "";
        links.navigation_hint = row.navigation_hint;
        linkDraft.draft.value.revision = row.revision;
        linkDraft.saved();
      }
    },
  );
  const round = reactive<components["schemas"]["RoundInput"]>({
      type: "technical",
      name: "技术一面",
      order: 1,
      status: "scheduled",
      planned_at: null,
      actual_at: null,
      deadline_at: null,
      location: "",
      reminders_enabled: false,
    }),
    editingRound =
      ref<Pick<components["schemas"]["RoundDTO"], "id" | "revision">>();
  const inputMemory = useDraft(
    () => `application-input:${id.value}`,
    () => ({
      profileId: profileId.value,
      missing: missing.value,
      confirmed: confirmed.value,
      submittedAt: submittedAt.value,
      observed: observed.value,
      target: target.value,
      eventType: eventType.value,
      reason: reason.value,
      taskAction: taskAction.value,
      round: clone(round),
      editingRound: editingRound.value
        ? { id: editingRound.value.id, revision: editingRound.value.revision }
        : null,
      baseRevision: 0,
    }),
  );
  const remembered = inputMemory.draft.value;
  profileId.value = remembered.profileId;
  missing.value = remembered.missing;
  confirmed.value = remembered.confirmed;
  submittedAt.value = remembered.submittedAt;
  observed.value = remembered.observed;
  target.value = remembered.target;
  eventType.value = remembered.eventType;
  reason.value = remembered.reason;
  taskAction.value = remembered.taskAction;
  Object.assign(round, remembered.round);
  editingRound.value = remembered.editingRound ?? undefined;
  watch(
    [
      profileId,
      missing,
      confirmed,
      submittedAt,
      observed,
      target,
      eventType,
      reason,
      taskAction,
      round,
      editingRound,
    ],
    () => {
      Object.assign(inputMemory.draft.value, {
        profileId: profileId.value,
        missing: missing.value,
        confirmed: confirmed.value,
        submittedAt: submittedAt.value,
        observed: observed.value,
        target: target.value,
        eventType: eventType.value,
        reason: reason.value,
        taskAction: taskAction.value,
        round: clone(round),
        editingRound: editingRound.value
          ? { id: editingRound.value.id, revision: editingRound.value.revision }
          : null,
      });
    },
    { deep: true, flush: "sync" },
  );
  watch(dialog, (value) => {
    if (value && !inputMemory.dirty.value) {
      inputMemory.draft.value.baseRevision = app.data.value?.revision ?? 0;
      inputMemory.saved();
    }
  });
  async function submit() {
    const row = app.data.value;
    if (!row) return;
    await act(async () => {
      if (Number.isNaN(Date.parse(submittedAt.value)))
        throw new Error("请填写有效的实际提交时间（含时区或本地时间）。");
      unwrap(
        await client.POST("/api/v1/applications/{app_id}/submissions", {
          params: { path: { app_id: id.value } },
          headers: key(),
          body: {
            expected_revision:
              inputMemory.draft.value.baseRevision || row.revision,
            actual_submission_confirmed: confirmed.value,
            submitted_at: new Date(submittedAt.value).toISOString(),
            channel: "本人官网提交",
            job_version_id: row.job_version_id,
            profile_version_id: profileId.value,
            missing_materials: missing.value,
          },
        }),
      );
      inputMemory.saved();
      dialog.value = "";
      await refresh();
    });
  }
  async function check() {
    const row = app.data.value;
    if (!row) return;
    await act(async () => {
      unwrap(
        await client.POST("/api/v1/applications/{app_id}/progress-checks", {
          params: { path: { app_id: id.value } },
          body: {
            expected_revision: row.revision,
            checked_at: new Date().toISOString(),
            observed_status: observed.value,
            changed: false,
            user_confirmed: true,
            company_status_kind: row.company_status_kind,
          },
        }),
      );
      inputMemory.saved();
      await refresh();
    });
  }
  async function stage() {
    const row = app.data.value;
    if (!row) return;
    await act(async () => {
      unwrap(
        await client.POST("/api/v1/applications/{app_id}/events", {
          params: { path: { app_id: id.value } },
          headers: key(),
          body: {
            expected_revision:
              inputMemory.draft.value.baseRevision || row.revision,
            event_type: eventType.value,
            to_stage: target.value,
            reason: reason.value,
            source: "本人记录",
            happened_at: new Date().toISOString(),
            close_reason: target.value === "closed" ? reason.value : null,
            task_action: taskAction.value,
          },
        }),
      );
      inputMemory.saved();
      dialog.value = "";
      await refresh();
    });
  }
  async function saveRound() {
    await act(async () => {
      if (editingRound.value) {
        unwrap(
          await client.PATCH("/api/v1/rounds/{round_id}", {
            params: { path: { round_id: editingRound.value.id } },
            body: {
              ...round,
              expected_revision: editingRound.value.revision,
              reason: reason.value || "本人改期或更新结果",
            },
          }),
        );
      } else {
        unwrap(
          await client.POST("/api/v1/applications/{app_id}/rounds", {
            params: { path: { app_id: id.value } },
            body: round,
          }),
        );
      }
      inputMemory.saved();
      dialog.value = "";
      await refresh();
    });
  }
  function editRound(row: components["schemas"]["RoundDTO"]) {
    editingRound.value = row;
    Object.assign(round, {
      type: row.type,
      name: row.name,
      order: row.order,
      status: row.status,
      planned_at: row.planned_at,
      actual_at: row.actual_at,
      deadline_at: row.deadline_at,
      location: row.location,
      reminders_enabled: row.reminders_enabled,
    });
    dialog.value = "round";
  }
  async function saveLinks() {
    const row = app.data.value;
    if (!row) return;
    await act(async () => {
      unwrap(
        await client.PATCH("/api/v1/applications/{app_id}", {
          params: { path: { app_id: id.value } },
          body: {
            expected_revision: linkDraft.draft.value.revision,
            ...links,
            job_url: links.job_url || null,
            apply_url: links.apply_url || null,
            progress_url: links.progress_url || null,
            company_status_raw: row.company_status_raw,
            company_status_kind: row.company_status_kind,
          },
        }),
      );
      linkDraft.saved();
      await refresh();
    });
  }
  async function prepare() {
    const row = app.data.value;
    if (!row) return;
    await act(async () => {
      const run = unwrap(
        await client.POST("/api/v1/applications/{app_id}/preparation-runs", {
          params: { path: { app_id: id.value } },
          body: { expected_revision: row.revision },
          headers: key(),
        }),
      );
      runId.value = run.id;
    });
  }
  async function changeBasis() {
    const row = app.data.value;
    if (!row) return;
    await act(async () => {
      unwrap(
        await client.POST("/api/v1/applications/{app_id}/preparation-basis", {
          params: { path: { app_id: id.value } },
          body: {
            expected_revision: row.revision,
            job_version_id: basisJobId.value ?? row.job_version_id,
            profile_version_id: profileId.value,
            reason: "本人显式切换准备资料",
          },
        }),
      );
      await refresh();
    });
  }

  function resetLinks() {
    const row = app.data.value;
    if (!row) return;
    Object.assign(links, {
      job_url: row.job_url ?? "",
      apply_url: row.apply_url ?? "",
      progress_url: row.progress_url ?? "",
      navigation_hint: row.navigation_hint,
    });
    linkDraft.draft.value.revision = row.revision;
    linkDraft.saved();
  }
  function resetInputs() {
    profileId.value = null;
    missing.value = true;
    confirmed.value = false;
    submittedAt.value = new Date().toISOString();
    observed.value = "";
    target.value = "preparing";
    eventType.value = "advance";
    reason.value = "";
    taskAction.value = "keep";
    Object.assign(round, {
      type: "technical",
      name: "技术一面",
      order: 1,
      status: "scheduled",
      planned_at: null,
      actual_at: null,
      deadline_at: null,
      location: "",
      reminders_enabled: false,
    });
    editingRound.value = undefined;
    dialog.value = "";
    inputMemory.draft.value.baseRevision = app.data.value?.revision ?? 0;
    inputMemory.saved();
  }
  return {
    id,
    app,
    rounds,
    events,
    submissions,
    bundles,
    profile,
    tasks,
    jobs,
    refresh,
    busy,
    error,
    runId,
    basisJobId,
    dialog,
    profileId,
    missing,
    confirmed,
    submittedAt,
    observed,
    target,
    eventType,
    reason,
    taskAction,
    links,
    linksDirty: linkDraft.dirty,
    inputsDirty: inputMemory.dirty,
    resetInputs,
    resetLinks,
    round,
    editingRound,
    submit,
    check,
    stage,
    saveRound,
    editRound,
    saveLinks,
    prepare,
    changeBasis,
  };
}
