import { Gauge, GitBranch, Lock, MonitorSmartphone, ShieldCheck, UserX } from "lucide-react";
import { retentionSentence } from "@/lib/config/retention";

const reasons = [
  {
    icon: ShieldCheck,
    title: "Privacy by design",
    text: retentionSentence,
  },
  {
    icon: UserX,
    title: "No account needed",
    text: "Use without signing up or providing an email address. Complete anonymity.",
  },
  {
    icon: Lock,
    title: "Isolated processing",
    text: "Documents are opened only inside sandboxed workers that cannot reach the internet.",
  },
  {
    icon: Gauge,
    title: "Fast and light",
    text: "A quick, simple site with no ads and no tracking scripts slowing you down.",
  },
  {
    icon: MonitorSmartphone,
    title: "Works everywhere",
    text: "Use it from any modern browser on your phone, tablet or computer. Nothing to install.",
  },
  {
    icon: GitBranch,
    title: "100% open source",
    text: "Full source code available. Self-host it or contribute improvements on GitHub.",
  },
] as const;

export function WhyChooseUs() {
  return (
    <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {reasons.map((reason) => (
        <li key={reason.title} className="flex gap-4">
          <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-fg">
            <reason.icon aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h3 className="font-semibold">{reason.title}</h3>
            <p className="mt-1 text-sm text-muted">{reason.text}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
