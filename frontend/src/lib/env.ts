/**
 * Public (NEXT_PUBLIC_*) configuration. These values are inlined into the
 * client bundle at build time, so they must never contain secrets.
 *
 * Production builds FAIL when a value is missing: there is no silent localhost
 * fallback outside development and tests. On Vercel the site URL may come from
 * VERCEL_PROJECT_PRODUCTION_URL (next.config.ts re-exports the resolved value
 * as NEXT_PUBLIC_SITE_URL so client code sees the same origin).
 */

const DEV_SITE_URL = "http://localhost:3000";
const DEV_API_BASE_URL = "http://localhost:8000";

export interface PublicEnv {
  NEXT_PUBLIC_SITE_URL?: string;
  NEXT_PUBLIC_API_BASE_URL?: string;
  VERCEL_PROJECT_PRODUCTION_URL?: string;
}

function present(value: string | undefined): value is string {
  return typeof value === "string" && value.trim() !== "";
}

/** Parses an http(s) URL and returns it without a trailing slash. */
export function parseBaseUrl(raw: string, name: string): string {
  let url: URL;
  try {
    url = new URL(raw.trim());
  } catch {
    throw new Error(`${name} must be an absolute http(s) URL`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`${name} must use http or https`);
  }
  return url.toString().replace(/\/+$/, "");
}

export function resolveSiteUrl(env: PublicEnv, isProduction: boolean): string {
  if (present(env.NEXT_PUBLIC_SITE_URL)) return parseBaseUrl(env.NEXT_PUBLIC_SITE_URL, "NEXT_PUBLIC_SITE_URL");
  if (present(env.VERCEL_PROJECT_PRODUCTION_URL)) {
    const host = env.VERCEL_PROJECT_PRODUCTION_URL.trim();
    return parseBaseUrl(/^https?:\/\//.test(host) ? host : `https://${host}`, "VERCEL_PROJECT_PRODUCTION_URL");
  }
  if (isProduction) {
    throw new Error("NEXT_PUBLIC_SITE_URL must be set for production builds (or VERCEL_PROJECT_PRODUCTION_URL on Vercel)");
  }
  return DEV_SITE_URL;
}

export function resolveApiBaseUrl(env: PublicEnv, isProduction: boolean): string {
  if (present(env.NEXT_PUBLIC_API_BASE_URL)) return parseBaseUrl(env.NEXT_PUBLIC_API_BASE_URL, "NEXT_PUBLIC_API_BASE_URL");
  if (isProduction) throw new Error("NEXT_PUBLIC_API_BASE_URL must be set for production builds");
  return DEV_API_BASE_URL;
}

const isProduction = process.env.NODE_ENV === "production";

// Each variable is referenced literally so Next.js can inline it.
/** Canonical origin of the website, used for metadataBase, canonical URLs and the sitemap. */
export const siteUrl = resolveSiteUrl(
  {
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL,
    VERCEL_PROJECT_PRODUCTION_URL: process.env.VERCEL_PROJECT_PRODUCTION_URL,
  },
  isProduction,
);

/** Base URL of the document API (browser uploads and downloads go here directly). */
export const apiBaseUrl = resolveApiBaseUrl({ NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL }, isProduction);

/** Builds an absolute URL on the site for a path such as `/tools`. */
export function absoluteUrl(path = "/"): string {
  return `${siteUrl}${path.startsWith("/") ? path : `/${path}`}`;
}
