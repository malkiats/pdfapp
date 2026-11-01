import { NextResponse, type NextRequest } from "next/server";
import { isKnownDynamicRoute } from "@/lib/routes";

/**
 * Returns a real 404 status for unknown /tools/{slug} and /categories/{slug}
 * URLs. Known slugs are prerendered; without this check an unknown slug would
 * be rendered on request and stream the not-found UI with a 200 status.
 */
export function proxy(request: NextRequest) {
  if (isKnownDynamicRoute(request.nextUrl.pathname)) return NextResponse.next();
  return NextResponse.rewrite(new URL("/__not-found", request.url), { status: 404 });
}

export const config = {
  matcher: ["/tools/:slug", "/categories/:slug"],
};
