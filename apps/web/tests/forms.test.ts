import { describe, it, expect, vi, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { readonly } from "vue";
import { createPinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import ElementPlus from "element-plus";
import Login from "../src/features/auth/Login.vue";
import { clone } from "../src/api/clone";

afterEach(() => vi.unstubAllGlobals());
describe("important interaction boundaries", () => {
  it("clones a readonly server snapshot into an independent draft", () => {
    const original = readonly({ facts: [{ text: "合成已确认事实" }] });
    const draft = clone(original);
    expect(draft).toEqual(original);
    expect(draft).not.toBe(original);
  });
  it("shows login failure without navigating or claiming success", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/login", component: Login },
        { path: "/jobs", component: { template: "<p>岗位</p>" } },
      ],
    });
    await router.push("/login");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) =>
        request.url.includes("/csrf")
          ? new Response(JSON.stringify({ csrf_token: "synthetic-csrf" }), {
              status: 200,
              headers: { "content-type": "application/json" },
            })
          : new Response(
              JSON.stringify({ error: { message: "用户名或密码错误" } }),
              { status: 401, headers: { "content-type": "application/json" } },
            ),
      ),
    );
    const wrapper = mount(Login, {
      global: { plugins: [createPinia(), router, ElementPlus] },
    });
    await flushPromises();
    await wrapper.get('[aria-label="用户名"]').setValue("synthetic");
    await wrapper.get('[aria-label="密码"]').setValue("wrong-password");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("用户名或密码错误");
    expect(router.currentRoute.value.path).toBe("/login");
    wrapper.unmount();
  });
});
