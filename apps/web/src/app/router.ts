import { createRouter, createWebHistory } from "vue-router";
import { useSession } from "./session";
export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, saved) {
    return saved ?? (to.path === from.path ? false : { top: 0 });
  },
  routes: [
    {
      path: "/reviews",
      component: () => import("../features/reviews/Reviews.vue"),
    },
    {
      path: "/operations",
      component: () => import("../features/operations/Operations.vue"),
    },
    {
      path: "/study",
      component: () => import("../features/interview/Study.vue"),
    },
    {
      path: "/study/:id",
      component: () => import("../features/interview/StudyDetail.vue"),
    },
    { path: "/today", component: () => import("../features/tasks/Today.vue") },
    {
      path: "/applications",
      component: () => import("../features/applications/Applications.vue"),
    },
    {
      path: "/applications/:id",
      component: () => import("../features/applications/ApplicationDetail.vue"),
    },
    {
      path: "/discover",
      component: () => import("../features/discovery/Discover.vue"),
    },
    { path: "/", redirect: "/today" },
    { path: "/login", component: () => import("../features/auth/Login.vue") },
    {
      path: "/profile",
      component: () => import("../features/profiles/Profile.vue"),
    },
    { path: "/jobs", component: () => import("../features/jobs/Jobs.vue") },
    {
      path: "/jobs/:id",
      component: () => import("../features/jobs/JobDetail.vue"),
    },
  ],
});
router.beforeEach(async (to) => {
  const tabChoices =
    to.path === "/profile"
      ? ["preferences", "facts", "history", "privacy"]
      : to.path === "/reviews"
        ? ["reviews", "offers"]
        : /^\/applications\/.+/.test(to.path)
          ? ["overview", "materials", "rounds", "practice", "tasks", "history"]
          : undefined;
  const rules: Record<string, readonly string[]> = {
    view: ["list", "board"],
    scope: ["recommended", "all"],
    difficulty: ["easy", "medium", "hard", "unknown"],
    sort: ["relevance", "difficulty", "detail"],
    stage: [
      "interested",
      "preparing",
      "submitted",
      "assessment",
      "offer",
      "onboarding",
      "closed",
    ],
    preference: ["priority", "interested", "unassigned", "paused", "excluded"],
    risk: ["unknown", "no_known_flags", "high_risk_flag"],
    eligibility: ["pass", "fail", "unknown"],
    fact_status: ["unconfirmed", "user_confirmed", "planned", "disputed"],
  };
  if (tabChoices) rules.tab = tabChoices;
  const query = { ...to.query };
  let changed = false;
  for (const [name, choices] of Object.entries(rules)) {
    const value = query[name];
    if (
      value !== undefined &&
      (typeof value !== "string" || !choices.includes(value))
    ) {
      delete query[name];
      changed = true;
    }
  }
  if (changed) return { path: to.path, hash: to.hash, query, replace: true };
  const session = useSession();
  if (to.path != "/login" && !session.user && !(await session.load()))
    return "/login";
});
