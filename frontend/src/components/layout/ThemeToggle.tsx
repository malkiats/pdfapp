"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useMounted } from "@/hooks/useMounted";

const ORDER = ["system", "light", "dark"] as const;
type ThemeChoice = (typeof ORDER)[number];

const LABELS: Record<ThemeChoice, string> = { system: "system", light: "light", dark: "dark" };
const ICONS = { system: Monitor, light: Sun, dark: Moon } as const;

export function nextTheme(current: string | undefined): ThemeChoice {
  const index = ORDER.indexOf((current ?? "system") as ThemeChoice);
  return ORDER[(index + 1) % ORDER.length] ?? "system";
}

/** Cycles system -> light -> dark. The label always states the current and next theme. */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();
  const current: ThemeChoice = mounted && ORDER.includes(theme as ThemeChoice) ? (theme as ThemeChoice) : "system";
  const next = nextTheme(current);
  const Icon = ICONS[current];
  const label = `Theme: ${LABELS[current]}. Switch to ${LABELS[next]} theme`;

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={label}
      title={label}
      className={`inline-flex size-11 items-center justify-center rounded-lg text-muted hover:bg-surface-strong hover:text-fg ${className}`}
    >
      <Icon aria-hidden="true" className="size-5" />
    </button>
  );
}
