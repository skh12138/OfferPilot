import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import OpportunityCard from "../src/features/discovery/OpportunityCard.vue";
import type { DiscoveryCard } from "../src/features/discovery/useDiscovery";

describe("recruitment evidence and prediction boundaries", () => {
  it("labels excerpt cards, unknown facts and predicted difficulty, and emits save intent", async () => {
    const opportunity: DiscoveryCard["opportunity"] = {
      title: "合成 Python 开发实习",
      company: "合成公司",
      cities: ["杭州"],
      requirements: ["了解 Python"],
      relevance: "high",
      relevance_reason: "方向相关",
      difficulty: {
        level: "medium",
        reason: "根据有限要求粗略估计",
        preparation: ["准备接口练习"],
      },
    };
    const candidate: DiscoveryCard["candidate"] = {
      id: "synthetic-candidate",
      url: "https://synthetic.example/job/1",
      title: opportunity.title,
      summary: "合成公司，了解 Python",
      query: "杭州 Python 实习",
      query_kind: "jobs",
      status: "metadata_only",
      error_code: null,
      job_id: null,
      created_at: "2026-10-23T00:00:00Z",
      intelligence: {
        kind: "position",
        opportunities: [opportunity],
        note: "合成样本",
        basis: "search_excerpt",
        prompt_version: "synthetic",
      },
    };
    const item = { id: "card", candidate, opportunity, sources: [candidate] };
    const wrapper = mount(OpportunityCard, {
      props: { item },
      global: { plugins: [ElementPlus], stubs: { RouterLink: true } },
    });
    expect(wrapper.text()).toContain("摘要整理 · 详情待核实");
    expect(wrapper.text()).toContain("薪资未说明");
    expect(wrapper.text()).toContain("AI 预测难度");
    expect(wrapper.text()).toContain("不代表企业面试标准或录用概率");
    expect(wrapper.get("a").attributes("href")).toBe(candidate.url);
    expect(wrapper.text()).not.toContain("查看岗位与证据");
    await wrapper.get("button").trigger("click");
    expect(wrapper.emitted("save")?.[0]?.[0]).toEqual(item);
    wrapper.unmount();
  });
});
