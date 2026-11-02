/**
 * Typed API client generated from shared/openapi.yaml (types in ./schema.d.ts).
 *
 * - Base URL comes from NEXT_PUBLIC_API_BASE_URL (public config, no secrets).
 * - No credentials: the API is anonymous and answers with `Access-Control-Allow-Origin: *`,
 *   which browsers refuse for credentialed requests.
 * - Synchronous tools: POST /api/v1/{tool-slug} returns the result in the response (no job polling).
 */
import createClient from "openapi-fetch";
import { apiBaseUrl } from "@/lib/env";
import type { paths } from "./schema";

export function createApiClient(baseUrl: string = apiBaseUrl) {
  return createClient<paths>({ baseUrl, credentials: "omit" });
}

export const api = createApiClient();

export type ApiClient = ReturnType<typeof createApiClient>;
