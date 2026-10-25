import { useRoute } from "vue-router";
import { computed, type Ref } from "vue";
import { useQuery, useQueryClient } from "@tanstack/vue-query";
import { client, unwrap } from "../../api/client";
import { useSession } from "../../app/session";
export function useApplication(id: Ref<string>) {
  const route = useRoute();
  const session = useSession(),
    cache = useQueryClient();
  const app = useQuery({
    queryKey: computed(() => ["application", session.user?.id, id.value]),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/applications/{app_id}", {
          params: { path: { app_id: id.value } },
        }),
      ),
  });
  const rounds = useQuery({
    queryKey: computed(() => ["rounds", session.user?.id, id.value]),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/applications/{app_id}/rounds", {
          params: { path: { app_id: id.value } },
        }),
      ),
  });
  const events = useQuery({
    enabled: computed(() => route.query.tab === "history"),
    queryKey: computed(() => ["events", session.user?.id, id.value]),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/applications/{app_id}/events", {
          params: { path: { app_id: id.value } },
        }),
      ),
  });
  const submissions = useQuery({
    enabled: computed(() => route.query.tab === "materials"),
    queryKey: computed(() => ["submissions", session.user?.id, id.value]),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/applications/{app_id}/submissions", {
          params: { path: { app_id: id.value } },
        }),
      ),
  });
  const bundles = useQuery({
    enabled: computed(() => route.query.tab === "materials"),
    queryKey: computed(() => ["bundles", session.user?.id, id.value]),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/applications/{app_id}/preparation-bundles", {
          params: { path: { app_id: id.value } },
        }),
      ),
  });
  const profile = useQuery({
    queryKey: ["profile", session.user?.id],
    queryFn: async () => unwrap(await client.GET("/api/v1/profiles/current")),
  });
  const tasks = useQuery({
    enabled: computed(() => route.query.tab === "tasks"),
    queryKey: computed(() => ["tasks", session.user?.id, id.value]),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/tasks", {
          params: { query: { application_id: id.value, limit: 100 } },
        }),
      ),
  });
  const jobs = useQuery({
    enabled: computed(() => route.query.tab === "materials"),
    queryKey: ["jobs", session.user?.id],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/jobs", { params: { query: { limit: 100 } } }),
      ),
  });
  async function refresh() {
    await cache.invalidateQueries({
      predicate: (q) =>
        [
          "application",
          "rounds",
          "events",
          "submissions",
          "bundles",
          "tasks",
          "jobs",
          "today",
          "applications",
        ].includes(String(q.queryKey[0])) &&
        (q.queryKey.includes(id.value) ||
          ["today", "applications"].includes(String(q.queryKey[0]))),
    });
  }
  return {
    app,
    rounds,
    events,
    submissions,
    bundles,
    profile,
    tasks,
    jobs,
    refresh,
  };
}
