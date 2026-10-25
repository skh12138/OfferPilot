import { defineStore } from "pinia";
import { ref } from "vue";
import type { components } from "../api/schema";
import { client, unwrap } from "../api/client";
export const useSession = defineStore("session", () => {
  const user = ref<components["schemas"]["UserDTO"]>();
  async function load() {
    const result = await client.GET("/api/v1/auth/me");
    user.value = result.data;
    return user.value;
  }
  async function logout() {
    unwrap(await client.POST("/api/v1/auth/logout"));
    user.value = undefined;
  }
  return { user, load, logout };
});
