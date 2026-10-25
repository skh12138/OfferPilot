import createClient from "openapi-fetch";
import type { paths } from "./schema";
export const client = createClient<paths>({
  baseUrl: typeof window !== "undefined" ? window.location.origin : "",
  fetch: (input: Request) => globalThis.fetch(input),
  credentials: "same-origin",
});
let csrf = "";
client.use({
  onResponse({ request, response }) {
    if (
      response.status === 401 &&
      !request.url.includes("/auth/") &&
      typeof window !== "undefined"
    )
      window.dispatchEvent(new Event("offerpilot:session-expired"));
  },
  onRequest({ request }) {
    if (!["GET", "HEAD"].includes(request.method)) {
      request.headers.set("X-CSRF-Token", csrf);
    }
    return request;
  },
});
export async function initCsrf() {
  const result = await client.GET("/api/v1/auth/csrf");
  csrf = unwrap(result).csrf_token;
}
export function key() {
  return { "Idempotency-Key": crypto.randomUUID() };
}
export function unwrap<T>(result: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (result.error || result.data === undefined) {
    const body = result.error as { error?: { message?: string } } | undefined;
    throw new Error(
      body?.error?.message ?? `请求失败 (${result.response.status})`,
    );
  }
  return result.data;
}
