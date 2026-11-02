"use client";

import { useId, useState } from "react";

type FieldType = "text" | "number" | "select" | "password" | "checkbox";

export interface ToolFieldSpec {
  /** Option name sent to the API in the `options` JSON (must match the backend). */
  name: string;
  label: string;
  type: FieldType;
  options?: { value: string; label: string }[];
  help?: string;
  placeholder?: string;
  defaultValue?: string | boolean;
  required?: boolean;
}

const PAGES_HELP = "Page numbers and ranges, for example 1-3,5,8-10.";
const PAGE_SIZE = {
  name: "page_size",
  label: "Page size",
  type: "select" as const,
  defaultValue: "fit",
  options: [
    { value: "fit", label: "Same as image" },
    { value: "a4", label: "A4" },
    { value: "letter", label: "US Letter" },
  ],
};
const DPI = {
  name: "dpi",
  label: "Resolution (DPI)",
  type: "number" as const,
  defaultValue: "110",
  help: "50-300. Higher is sharper but makes larger files.",
};
const IMAGE_PAGES = { name: "pages", label: "Pages (optional)", type: "text" as const, help: `Leave blank for all pages. ${PAGES_HELP}` };
const SUMMARY_LENGTH = {
  name: "length",
  label: "Summary length",
  type: "select" as const,
  defaultValue: "medium",
  options: [
    { value: "short", label: "Short" },
    { value: "medium", label: "Medium" },
    { value: "long", label: "Long" },
  ],
};
const TARGET_LANGUAGE = {
  name: "target_language",
  label: "Translate into",
  type: "text" as const,
  placeholder: "e.g. French, Spanish, German",
  required: true,
};

/** Option fields per tool. Names and values match the backend (backend/app/lib). */
export const TOOL_FIELDS: Record<string, ToolFieldSpec[]> = {
  "merge-pdf": [{ name: "keep_bookmarks", label: "Keep bookmarks", type: "checkbox", defaultValue: true }],
  "split-pdf": [
    {
      name: "ranges",
      label: "Page ranges",
      type: "text",
      help: "Each comma-separated part becomes one file, e.g. 1-3,4-6,7. Or leave blank and use the next field.",
    },
    { name: "every_n", label: "Or: split every N pages", type: "number", placeholder: "e.g. 1" },
  ],
  "remove-pages": [{ name: "pages", label: "Pages to remove", type: "text", help: PAGES_HELP, required: true }],
  "extract-pages": [{ name: "pages", label: "Pages to extract", type: "text", help: PAGES_HELP, required: true }],
  "organize-pdf": [
    {
      name: "page_order",
      label: "New page order",
      type: "text",
      help: "List every page you want to keep, in the new order, e.g. 3,1,2. Repeat a page to duplicate it.",
      required: true,
    },
  ],
  "scan-to-pdf": [PAGE_SIZE],
  "jpg-to-pdf": [PAGE_SIZE],
  "png-to-pdf": [PAGE_SIZE],
  "compress-pdf": [
    {
      name: "level",
      label: "Compression",
      type: "select",
      defaultValue: "medium",
      options: [
        { value: "low", label: "Low (best quality)" },
        { value: "medium", label: "Medium (recommended)" },
        { value: "high", label: "High (smallest file)" },
      ],
    },
  ],
  "pdf-to-jpg": [DPI, IMAGE_PAGES],
  "pdf-to-png": [DPI, IMAGE_PAGES],
  "rotate-pdf": [
    {
      name: "angle",
      label: "Rotate clockwise by",
      type: "select",
      defaultValue: "90",
      options: [
        { value: "90", label: "90°" },
        { value: "180", label: "180°" },
        { value: "270", label: "270°" },
      ],
    },
    { name: "pages", label: "Pages to rotate (optional)", type: "text", help: `Leave blank for all pages. ${PAGES_HELP}` },
  ],
  "add-page-numbers": [
    {
      name: "position",
      label: "Position",
      type: "select",
      defaultValue: "bottom-center",
      options: [
        { value: "bottom-center", label: "Bottom center" },
        { value: "bottom-right", label: "Bottom right" },
        { value: "bottom-left", label: "Bottom left" },
        { value: "top-center", label: "Top center" },
        { value: "top-right", label: "Top right" },
        { value: "top-left", label: "Top left" },
      ],
    },
    {
      name: "format",
      label: "Format",
      type: "select",
      defaultValue: "n",
      options: [
        { value: "n", label: "1" },
        { value: "page-n", label: "Page 1" },
        { value: "page-n-of-total", label: "Page 1 of 10" },
        { value: "n-of-total", label: "1 / 10" },
      ],
    },
    { name: "start", label: "Start at", type: "number", defaultValue: "1" },
  ],
  "add-watermark": [
    { name: "text", label: "Watermark text", type: "text", placeholder: "e.g. CONFIDENTIAL", required: true },
    {
      name: "layout",
      label: "Layout",
      type: "select",
      defaultValue: "diagonal",
      options: [
        { value: "diagonal", label: "Diagonal" },
        { value: "horizontal", label: "Horizontal" },
      ],
    },
    { name: "opacity", label: "Opacity (%)", type: "number", defaultValue: "25", help: "5-100" },
  ],
  "crop-pdf": [
    { name: "margin_mm", label: "Trim from each edge (mm)", type: "number", defaultValue: "10", help: "0-200 mm." },
  ],
  "unlock-pdf": [{ name: "password", label: "Current password", type: "password", required: true }],
  "protect-pdf": [
    { name: "password", label: "New password", type: "password", help: "At least 4 characters.", required: true },
    { name: "allow_printing", label: "Allow printing", type: "checkbox", defaultValue: true },
    { name: "allow_copying", label: "Allow copying text", type: "checkbox", defaultValue: false },
  ],
  "summarize-pdf": [SUMMARY_LENGTH],
  "summarize-article": [SUMMARY_LENGTH],
  "translate-pdf": [TARGET_LANGUAGE],
  "translate-text": [TARGET_LANGUAGE],
  "ask-pdf": [{ name: "question", label: "Your question", type: "text", placeholder: "What is the deadline?", required: true }],
};

/** Initial options for a tool (field defaults), so the API always gets explicit values. */
export function defaultOptions(toolSlug: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const field of TOOL_FIELDS[toolSlug] ?? []) {
    if (field.defaultValue !== undefined) result[field.name] = field.defaultValue;
  }
  return result;
}

/** Names of required fields that are still empty. */
export function missingRequired(toolSlug: string, options: Record<string, unknown>): string[] {
  return (TOOL_FIELDS[toolSlug] ?? [])
    .filter((f) => f.required && (options[f.name] === undefined || String(options[f.name]).trim() === ""))
    .map((f) => f.label);
}

export function ToolForm({
  toolSlug,
  disabled,
  onOptionsChange,
}: {
  toolSlug?: string;
  disabled?: boolean;
  onOptionsChange: (options: Record<string, unknown>) => void;
}) {
  const fields = toolSlug ? TOOL_FIELDS[toolSlug] : undefined;
  const [formState, setFormState] = useState<Record<string, unknown>>(() => (toolSlug ? defaultOptions(toolSlug) : {}));

  if (!fields || fields.length === 0) return null;

  const handleFieldChange = (fieldName: string, value: unknown) => {
    const next = { ...formState };
    if (value === undefined || value === "") delete next[fieldName];
    else next[fieldName] = value;
    setFormState(next);
    onOptionsChange(next);
  };

  return (
    <fieldset disabled={disabled} className="space-y-4 rounded-2xl border border-border bg-surface p-5">
      <legend className="px-1 text-sm font-semibold">Options</legend>
      {fields.map((field) => (
        <ToolFormField
          key={field.name}
          field={field}
          value={formState[field.name]}
          onValueChange={(value) => handleFieldChange(field.name, value)}
        />
      ))}
    </fieldset>
  );
}

const fieldClass =
  "mt-1 h-11 w-full rounded-lg border border-border-strong bg-bg px-3 disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted";

function ToolFormField({
  field,
  value,
  onValueChange,
}: {
  field: ToolFieldSpec;
  value: unknown;
  onValueChange: (value: unknown) => void;
}) {
  const id = useId();
  const helpId = `${id}-help`;
  const help = field.help ? (
    <p id={helpId} className="mt-0.5 text-xs text-muted">
      {field.help}
    </p>
  ) : null;

  if (field.type === "checkbox") {
    return (
      <label htmlFor={id} className="flex min-h-11 cursor-pointer items-center gap-3 text-sm font-medium">
        <input
          id={id}
          type="checkbox"
          checked={value === true}
          onChange={(e) => onValueChange(e.target.checked)}
          className="size-5 accent-accent"
        />
        {field.label}
      </label>
    );
  }

  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium">
        {field.label}
        {field.required ? <span className="text-danger"> *</span> : null}
      </label>
      {help}
      {field.type === "select" && field.options ? (
        <select
          id={id}
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onValueChange(e.target.value)}
          className={fieldClass}
          aria-describedby={field.help ? helpId : undefined}
        >
          {field.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          type={field.type === "password" ? "password" : field.type === "number" ? "number" : "text"}
          inputMode={field.type === "number" ? "numeric" : undefined}
          autoComplete={field.type === "password" ? "off" : undefined}
          value={typeof value === "string" ? value : ""}
          placeholder={field.placeholder}
          required={field.required}
          onChange={(e) => onValueChange(e.target.value)}
          className={fieldClass}
          aria-describedby={field.help ? helpId : undefined}
        />
      )}
    </div>
  );
}
