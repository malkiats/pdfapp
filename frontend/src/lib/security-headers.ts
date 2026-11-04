/**
 * Security headers applied to every route by next.config.ts.
 *
 * CSP notes:
 * - Pages are statically generated, so per-request nonces are not possible
 *   without making every page dynamic. Next.js and next-themes emit small
 *   inline bootstrap scripts, which is why script-src keeps 'unsafe-inline'.
 *   There are no third-party scripts and no user-generated HTML, which limits
 *   the XSS surface. Revisit with nonces (proxy) once dynamic, signed-in pages
 *   ship (see README "Security headers").
 * - connect-src allows only this origin, the API origin from
 *   NEXT_PUBLIC_API_BASE_URL (browser uploads/downloads go there directly) and
 *   the large-file storage origins from NEXT_PUBLIC_UPLOAD_ORIGINS (presigned PUTs).
 */

export interface SecurityHeaderOptions {
  apiBaseUrl: string;
  isDev: boolean;
  /** Storage origins that receive presigned PUTs (large-file flow). */
  uploadOrigins?: readonly string[];
}

/** Refuses anything but a plain http(s) origin, so config can never inject CSP syntax or wildcards. */
export function assertPlainOrigin(source: string): string {
  if (/[\s;,*'"]/.test(source)) throw new Error("CSP source must be a plain origin");
  let url: URL;
  try {
    url = new URL(source);
  } catch {
    throw new Error("CSP source must be a plain origin");
  }
  if ((url.protocol !== "https:" && url.protocol !== "http:") || url.origin !== source) {
    throw new Error("CSP source must be a plain origin");
  }
  return source;
}

export function buildCsp({ apiBaseUrl, isDev, uploadOrigins = [] }: SecurityHeaderOptions): string {
  const apiOrigin = assertPlainOrigin(new URL(apiBaseUrl).origin);
  uploadOrigins.forEach(assertPlainOrigin);
  const apiIsHttps = apiOrigin.startsWith("https://");
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", ...(isDev ? ["'unsafe-eval'"] : [])],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:"],
    "font-src": ["'self'"],
    "connect-src": ["'self'", apiOrigin, ...uploadOrigins, ...(isDev ? ["ws:", "wss:"] : [])],
    "media-src": ["'self'"],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
    "object-src": ["'none'"],
    "frame-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  const parts = Object.entries(directives).map(([name, values]) => `${name} ${[...new Set(values)].join(" ")}`);
  // Only upgrade when the API is HTTPS too, otherwise local http API calls would break.
  if (!isDev && apiIsHttps) parts.push("upgrade-insecure-requests");
  return parts.join("; ");
}

export function securityHeaders(options: SecurityHeaderOptions): { key: string; value: string }[] {
  return [
    { key: "Content-Security-Policy", value: buildCsp(options) },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    {
      key: "Permissions-Policy",
      value:
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=(), bluetooth=(), hid=(), midi=(), magnetometer=(), gyroscope=(), accelerometer=(), browsing-topics=()",
    },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
    { key: "X-DNS-Prefetch-Control", value: "off" },
    ...(options.isDev
      ? []
      : [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]),
  ];
}
