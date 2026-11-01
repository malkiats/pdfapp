import { serializeJsonLd, type JsonLd as JsonLdData } from "@/lib/seo";

/** Renders structured data. Content is escaped by serializeJsonLd. */
export function JsonLd({ data }: { data: JsonLdData | JsonLdData[] }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(data) }} />;
}
