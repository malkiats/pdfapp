import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { retentionSentence } from "@/lib/config/retention";

const SRC = path.resolve(import.meta.dirname, "../../src");
const BANNED = [/always within/i, /as soon as/i, /straight away/i, /nothing is kept longer/i, /zero retention"/i];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return files(full);
    return /\.(ts|tsx)$/.test(name) && !name.endsWith("schema.d.ts") ? [full] : [];
  });
}

describe("retention copy guard", () => {
  it("uses the approved retention sentence", () => {
    expect(retentionSentence).toBe(
      "Files are deleted automatically, usually within minutes of your download and no later than about 2 hours after processing.",
    );
  });

  it.each(BANNED.map((re) => [re.source, re] as const))("no source file contains %s", (_label, re) => {
    const offenders = files(SRC).filter((file) => re.test(readFileSync(file, "utf8")));
    expect(offenders).toEqual([]);
  });
});
