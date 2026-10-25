import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent } from "vue";
describe("plain text boundary", () => {
  it("renders hostile text without interpreting markup", () => {
    const c = mount(
      defineComponent({
        props: ["text"],
        template: "<blockquote>{{text}}</blockquote>",
      }),
      { props: { text: "<img src=x onerror=alert(1)>" } },
    );
    expect(c.find("img").exists()).toBe(false);
    expect(c.text()).toContain("<img");
  });
});
