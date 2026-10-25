import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useQuery } from "@tanstack/vue-query";
import type { components } from "../../api/schema";
import { client, key, unwrap } from "../../api/client";
import { useSession } from "../../app/session";
import { useAction } from "../../app/action";
import { useChoiceQuery, useListPosition } from "../../app/navigation";
import { useDraft } from "../../app/ui";

type Candidate = components["schemas"]["CandidateDTO"];
export interface DiscoveryCard {
  id: string;
  candidate: Candidate;
  opportunity: components["schemas"]["Opportunity"];
  sources: Candidate[];
}
const terminal = ["succeeded", "partial", "failed", "cancelled"];
export const difficultyLabels: Record<string, string> = {
  easy: "入门友好",
  medium: "适中",
  hard: "偏难",
  unknown: "信息不足",
};
export function useDiscovery() {
  const route = useRoute(),
    router = useRouter(),
    session = useSession();
  const { busy, error, act } = useAction();
  const searchDraft = useDraft("discovery-input", () => ({ text: "" }));
  const text = computed({
      get: () => searchDraft.draft.value.text,
      set: (value) => {
        searchDraft.draft.value.text = value;
      },
    }),
    publicConsent = ref(true),
    difficulty = useChoiceQuery(
      "difficulty",
      ["", "easy", "medium", "hard", "unknown"],
      "",
    ),
    sort = useChoiceQuery(
      "sort",
      ["relevance", "difficulty", "detail"],
      "relevance",
    ),
    scope = useChoiceQuery("scope", ["recommended", "all"], "recommended");
  const runId = computed(() => String(route.query.run ?? ""));
  const organizeId = computed(() => String(route.query.organize ?? ""));
  const progressId = computed(() => organizeId.value || runId.value);
  const capability = useQuery({
    queryKey: ["capabilities"],
    queryFn: async () => unwrap(await client.GET("/api/v1/capabilities")),
  });
  const specs = useQuery({
    queryKey: ["specs", session.user?.id],
    queryFn: async () => unwrap(await client.GET("/api/v1/search-specs")),
  });
  const progress = useQuery({
    queryKey: computed(() => ["run", session.user?.id, progressId.value]),
    enabled: computed(() => !!progressId.value),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/runs/{run_id}", {
          params: { path: { run_id: progressId.value } },
        }),
      ),
    refetchInterval: false,
  });
  const running = computed(
    () =>
      !!progressId.value &&
      !terminal.includes(progress.data.value?.status ?? ""),
  );
  const candidates = useQuery({
    queryKey: computed(() => ["candidates", session.user?.id, runId.value]),
    enabled: computed(() => !!runId.value),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/v1/search-runs/{run_id}/candidates", {
          params: { path: { run_id: runId.value } },
        }),
      ),
    refetchInterval: computed(() => (running.value ? 2500 : false)),
  });
  useListPosition(computed(() => !candidates.isPending.value));
  const cards = computed(() => {
    const grouped = new Map<string, DiscoveryCard>();
    for (const candidate of candidates.data.value?.items ?? []) {
      for (const [index, opportunity] of (
        candidate.intelligence?.opportunities ?? []
      ).entries()) {
        const identity = [
          opportunity.company || candidate.url,
          opportunity.title,
          [...(opportunity.cities ?? [])].sort().join(","),
        ]
          .join("|")
          .replace(/\s+/g, "")
          .toLowerCase();
        const previous = grouped.get(identity);
        if (previous) {
          previous.sources.push(candidate);
          if (
            candidate.intelligence?.basis === "job_text" &&
            previous.candidate.intelligence?.basis !== "job_text"
          ) {
            previous.candidate = candidate;
            previous.opportunity = opportunity;
          }
        } else
          grouped.set(identity, {
            id: `${candidate.id}-${index}`,
            candidate,
            opportunity,
            sources: [candidate],
          });
      }
    }
    return [...grouped.values()];
  });
  const visibleCards = computed(() =>
    cards.value
      .filter(
        (c) =>
          (scope.value !== "recommended" ||
            c.opportunity.relevance !== "low") &&
          (!difficulty.value ||
            c.opportunity.difficulty?.level === difficulty.value),
      )
      .sort((a, b) => {
        const levels: Record<string, number> = {
          easy: 0,
          medium: 1,
          hard: 2,
          unknown: 3,
          high: 0,
          possible: 1,
          low: 2,
        };
        if (sort.value === "difficulty")
          return (
            (levels[a.opportunity.difficulty?.level ?? "unknown"] ?? 3) -
            (levels[b.opportunity.difficulty?.level ?? "unknown"] ?? 3)
          );
        if (sort.value === "detail")
          return (
            Number(b.candidate.intelligence?.basis === "job_text") -
            Number(a.candidate.intelligence?.basis === "job_text")
          );
        return (
          (levels[a.opportunity.relevance ?? "possible"] ?? 1) -
          (levels[b.opportunity.relevance ?? "possible"] ?? 1)
        );
      }),
  );
  const leftovers = computed(
    () =>
      candidates.data.value?.items.filter(
        (c) => !c.intelligence?.opportunities.length,
      ) ?? [],
  );
  const fullCount = computed(
    () =>
      cards.value.filter((c) => c.candidate.intelligence?.basis === "job_text")
        .length,
  );
  const draft = ref<components["schemas"]["SpecInput"]>({
    keywords: "",
    cities: [],
    confirmed: false,
    max_queries: 3,
    max_results: 8,
    max_extracts: 6,
    employment_type: "internship",
    raw_keywords: "",
    natural_language: false,
  });
  async function naturalSearch() {
    await act(async () => {
      const run = unwrap(
        await client.POST("/api/v1/search-runs/natural", {
          headers: key(),
          body: {
            text: text.value.trim(),
            public_info_ai_consent: publicConsent.value,
            max_queries: draft.value.max_queries ?? 3,
            max_results: 8,
            max_extracts: 6,
          },
        }),
      );
      searchDraft.saved();
      await router.replace({
        query: {
          ...route.query,
          run: run.id,
          organize: undefined,
          selected: undefined,
        },
      });
      await specs.refetch();
    });
  }
  async function search(specId?: string) {
    await act(async () => {
      const id =
        specId ||
        unwrap(await client.POST("/api/v1/search-specs", { body: draft.value }))
          .id;
      const run = unwrap(
        await client.POST("/api/v1/search-runs", {
          headers: key(),
          body: { spec_id: id, public_info_ai_consent: publicConsent.value },
        }),
      );
      await router.replace({
        query: {
          ...route.query,
          run: run.id,
          organize: undefined,
          selected: undefined,
        },
      });
      await specs.refetch();
    });
  }
  async function organize() {
    await act(async () => {
      const run = unwrap(
        await client.POST("/api/v1/search-runs/{run_id}/organize", {
          params: { path: { run_id: runId.value } },
          headers: key(),
          body: { public_info_ai_consent: publicConsent.value },
        }),
      );
      await router.replace({ query: { ...route.query, organize: run.id } });
    });
  }
  const intent = reactive({
    open: false,
    title: "",
    company: "",
    candidate: undefined as Candidate | undefined,
  });
  function startIntent(card: DiscoveryCard) {
    intent.title = card.opportunity.title;
    intent.company = card.opportunity.company ?? "";
    intent.candidate = card.candidate;
    intent.open = true;
  }
  async function saveIntent() {
    await act(async () => {
      const candidate = intent.candidate;
      if (!candidate) return;
      const version = candidate.job_id
        ? unwrap(
            await client.GET("/api/v1/jobs/{job_id}", {
              params: { path: { job_id: candidate.job_id } },
            }),
          ).current_version_id
        : null;
      const application = unwrap(
        await client.POST("/api/v1/applications", {
          headers: key(),
          body: {
            title: intent.title,
            company: intent.company,
            job_version_id: version,
            job_url: candidate.url,
            navigation_hint:
              candidate.intelligence?.basis === "job_text"
                ? "由找岗结果保存意向，请到原站确认后投递"
                : "由AI整理的搜索线索保存意向；完整JD与招聘有效性待本人核实",
            allow_reapply: false,
          },
        }),
      );
      await router.push(`/applications/${application.id}`);
    });
  }
  return {
    text,
    publicConsent,
    difficulty,
    sort,
    scope,
    runId,
    progressId,
    progress,
    running,
    capability,
    specs,
    candidates,
    cards,
    visibleCards,
    leftovers,
    fullCount,
    draft,
    busy,
    error,
    naturalSearch,
    search,
    organize,
    intent,
    startIntent,
    saveIntent,
  };
}
