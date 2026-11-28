import Link from "next/link";
import {
  ArrowRight,
  Combine,
  EyeOff,
  FileDown,
  FileText,
  GitBranch,
  Image as ImageIcon,
  Lock,
  PenLine,
  ScanText,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserX,
} from "lucide-react";
import { siteConfig } from "@/lib/config/site";

/** Tasks phrased the way people think of them, each linking to the tool that does it. */
const TASKS = [
  { href: "/tools/compress-pdf", label: "Make a PDF smaller", icon: FileDown },
  { href: "/tools/merge-pdf", label: "Combine PDFs into one", icon: Combine },
  { href: "/tools/pdf-to-word", label: "Edit a PDF in Word", icon: FileText },
  { href: "/tools/jpg-to-pdf", label: "Turn photos into a PDF", icon: ImageIcon },
  { href: "/tools/sign-pdf", label: "Sign a PDF", icon: PenLine },
  { href: "/tools/protect-pdf", label: "Add a password", icon: Lock },
  { href: "/tools/summarize-pdf", label: "Summarize with AI", icon: Sparkles },
  { href: "/tools/image-to-text", label: "Copy text from an image", icon: ScanText },
] as const;

/** Verifiable facts only (see /security and /privacy). */
const TRUST = [
  { icon: ShieldCheck, label: "HTTPS only" },
  { icon: Trash2, label: "Files deleted automatically" },
  { icon: EyeOff, label: "No ads or trackers" },
  { icon: UserX, label: "No account needed" },
  { icon: GitBranch, label: "Open source", href: siteConfig.sourceUrl },
] as const;

export function StartHere() {
  return (
    <div>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {TASKS.map((task) => (
          <li key={task.href}>
            <Link
              href={task.href}
              className="group flex min-h-14 items-center gap-3 rounded-xl border border-border bg-bg px-4 py-3 font-medium transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-md motion-reduce:transform-none"
            >
              <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-fg">
                <task.icon aria-hidden="true" className="size-5" />
              </span>
              <span className="flex-1">{task.label}</span>
              <ArrowRight aria-hidden="true" className="size-4 text-accent transition-transform group-hover:translate-x-1" />
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-6 text-sm text-muted">
        Working with lots of files? Merge PDF and JPG to PDF take up to 20 files at once. New here?{" "}
        <Link href="/guides" className="font-medium text-accent underline underline-offset-4">
          Read the step-by-step guides
        </Link>
        .
      </p>
      <ul aria-label="Why you can trust this site" className="mt-8 flex flex-wrap gap-x-6 gap-y-3 border-t border-border pt-6 text-sm text-muted">
        {TRUST.map((item) => (
          <li key={item.label} className="inline-flex items-center gap-2">
            <item.icon aria-hidden="true" className="size-4 text-success" />
            {"href" in item ? (
              <a href={item.href} className="hover:text-fg hover:underline">
                {item.label}
              </a>
            ) : (
              item.label
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
