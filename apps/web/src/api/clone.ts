/** DTOs contain JSON values only; clone Vue readonly proxies into editable form drafts. */
export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
