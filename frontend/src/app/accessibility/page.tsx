import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { PageHeader } from "@/components/ui/PageHeader";
import { PlaceholderTag } from "@/components/ui/PlaceholderTag";
import { Prose } from "@/components/ui/Prose";
import { siteConfig } from "@/lib/config/site";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Accessibility and keyboard shortcuts",
  description: `How ${siteConfig.name} supports keyboard and screen reader users, the keyboard shortcuts, and which browsers are supported.`,
  path: "/accessibility",
});

const shortcuts: readonly [string, string][] = [
  ["/", "Jump to the tool search (opens the tools list if the page has no search box)"],
  ["Enter (in search)", "Open the first matching tool"],
  ["↓ / ↑ (in search)", "Move through the search results"],
  ["Esc (in search)", "Clear the search and return to the input"],
  ["Tab / Shift+Tab", "Move between links, buttons and form fields"],
  ["Enter or Space", "Activate the focused button, such as Choose files"],
];

const kbd = "rounded border border-border-strong bg-surface px-1.5 py-0.5 font-mono text-xs text-fg";

export default function AccessibilityPage() {
  return (
    <>
      <PageHeader
        title="Accessibility"
        description="Everyone should be able to use these tools, with a mouse, a keyboard or a screen reader."
      />
      <Container className="py-12">
        <Prose>
          <h2>Our goal</h2>
          <p>
            We aim to meet the Web Content Accessibility Guidelines (WCAG) 2.2 at level AA. We have not had an
            independent audit, so some things may still fall short. Please tell us when they do.
          </p>
          <h2>What we have built in</h2>
          <ul>
            <li>Every tool works with the keyboard alone, including choosing files (no drag and drop needed).</li>
            <li>A &quot;Skip to main content&quot; link, visible focus outlines and clear headings on every page.</li>
            <li>Progress, results and errors are announced to screen readers; errors receive focus.</li>
            <li>Text and controls meet AA contrast in both the light and dark themes.</li>
            <li>
              Light, dark or system theme: use the theme button in the header (in the menu on small screens). Your choice
              is remembered on your device.
            </li>
            <li>Layouts are designed to work when zoomed to 200% and on small screens.</li>
          </ul>
        </Prose>

        <section aria-labelledby="shortcuts-title" className="mt-10 max-w-3xl">
          <h2 id="shortcuts-title" className="text-2xl font-semibold">
            Keyboard shortcuts
          </h2>
          <table className="mt-4 w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th scope="col" className="py-2 pr-4 font-semibold">
                  Key
                </th>
                <th scope="col" className="py-2 font-semibold">
                  What it does
                </th>
              </tr>
            </thead>
            <tbody>
              {shortcuts.map(([key, action]) => (
                <tr key={key} className="border-b border-border">
                  <td className="py-2 pr-4 align-top whitespace-nowrap">
                    <kbd className={kbd}>{key}</kbd>
                  </td>
                  <td className="py-2 text-muted">{action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <div className="mt-10">
          <Prose>
            <h2>Supported browsers</h2>
            <p>
              The site is built for the current versions of Chrome, Edge, Firefox and Safari, on desktop and on mobile
              (Android and iOS). Older browsers may work but are not tested. Nothing needs to be installed.
            </p>
            <h2>Feedback</h2>
            <p>
              If something is hard to use, email <a href={`mailto:${siteConfig.contactEmail}`}>{siteConfig.contactEmail}</a>
              <PlaceholderTag /> or see <Link href="/contact">other ways to contact us</Link>.
            </p>
          </Prose>
        </div>
      </Container>
    </>
  );
}
