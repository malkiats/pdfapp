import path from "node:path";
import type { NextConfig } from "next";
import { apiBaseUrl, siteUrl } from "./src/lib/env";
import { securityHeaders } from "./src/lib/security-headers";

/**
 * Monorepo root. The app imports ../shared/tool-catalog.json at build time, so
 * Turbopack and output file tracing must be allowed to read outside frontend/.
 * On Vercel (Root Directory = frontend) keep "Include files outside the root
 * directory in the Build Step" enabled. See README.md.
 */
const monorepoRoot = path.resolve(__dirname, "..");

const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  // Re-export the resolved values so server and client code see the same origins
  // (the site URL may come from VERCEL_PROJECT_PRODUCTION_URL, see src/lib/env.ts).
  env: {
    NEXT_PUBLIC_SITE_URL: siteUrl,
    NEXT_PUBLIC_API_BASE_URL: apiBaseUrl,
  },
  reactStrictMode: true,
  outputFileTracingRoot: monorepoRoot,
  turbopack: {
    root: monorepoRoot,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders({ apiBaseUrl, isDev }),
      },
    ];
  },
};

export default nextConfig;
