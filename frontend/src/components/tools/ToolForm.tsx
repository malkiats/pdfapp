"use client";

import { useId, useState } from "react";

const TOOL_FIELDS: Record<string, ToolFieldSpec[]> = {
  "merge-pdf": [
    { name: "order", label: "Page order", type: "text", help: "Comma-separated page numbers (e.g., 1,3,2)" },
  ],
  "split-pdf": [
    { name: "pages", label: "Pages to split", type: "text", help: "Page ranges (e.g., 1-3,5,8-10)" },
  ],
  "organize-pdf": [
    { name: "page_order", label: "Page order", type: "text", help: "Comma-separated page numbers" },
  ],
  "rotate-pdf": [
    { name: "angle", label: "Rotation (degrees)", type: "select", options: ["90", "180", "270"] },
    { name: "pages", label: "Pages to rotate", type: "text", help: "Leave blank for all pages" },
  ],
  "compress-pdf": [
    { name: "level", label: "Compression level", type: "select", options: ["low", "medium", "high"] },
  ],
  "image-to-pdf": [
    { name: "order", label: "Image order", type: "text", help: "Comma-separated image numbers" },
  ],
  "pdf-to-images": [
    { name: "format", label: "Image format", type: "select", options: ["png", "jpg"] },
    { name: "dpi", label: "DPI", type: "number" },
  ],
  "extract-text": [
    { name: "format", label: "Output format", type: "select", options: ["txt", "json"] },
  ],
};

interface ToolFieldSpec {
  name: string;
  label: string;
  type: "text" | "number" | "select";
  options?: string[];
  help?: string;
}

/**
 * Phase 2: Auto-generated form based on tool-specific field specs.
 * Parses comma-separated text into arrays where needed.
 */
export function ToolForm({
  toolSlug,
  onOptionsChange,
}: {
  toolSlug?: string;
  onOptionsChange: (options: Record<string, unknown>) => void;
}) {
  const fields = toolSlug ? TOOL_FIELDS[toolSlug] : undefined;
  const [formState, setFormState] = useState<Record<string, unknown>>({});

  if (!fields || fields.length === 0) return null;

  const handleFieldChange = (fieldName: string, value: unknown) => {
    const newState = { ...formState, [fieldName]: value };
    setFormState(newState);
    onOptionsChange(newState);
  };

  return (
    <fieldset className="space-y-4 rounded-2xl border border-border bg-surface p-5">
      <legend className="text-sm font-semibold">Options</legend>
      {fields.map((field) => (
        <ToolFormField
          key={field.name}
          field={field}
          onValueChange={(value) => handleFieldChange(field.name, value)}
        />
      ))}
    </fieldset>
  );
}

function ToolFormField({
  field,
  onValueChange,
}: {
  field: ToolFieldSpec;
  onValueChange: (value: unknown) => void;
}) {
  const id = useId();
  const fieldClass =
    "mt-1 h-11 w-full rounded-lg border border-border-strong bg-bg px-3 disabled:cursor-not-allowed disabled:bg-surface-strong disabled:text-muted";

  if (field.type === "select" && field.options) {
    return (
      <div>
        <label htmlFor={id} className="text-sm font-medium">
          {field.label}
        </label>
        <select
          id={id}
          onChange={(e) => onValueChange(e.target.value || undefined)}
          className={fieldClass}
        >
          <option value="">-- Select {field.label.toLowerCase()} --</option>
          {field.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt.charAt(0).toUpperCase() + opt.slice(1)}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (field.type === "number") {
    return (
      <div>
        <label htmlFor={id} className="text-sm font-medium">
          {field.label}
        </label>
        {field.help && <p className="mt-0.5 text-xs text-muted">{field.help}</p>}
        <input
          id={id}
          type="number"
          onChange={(e) => {
            const val = e.target.value;
            onValueChange(val === "" ? undefined : parseInt(val, 10));
          }}
          className={fieldClass}
        />
      </div>
    );
  }

  // text input
  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium">
        {field.label}
      </label>
      {field.help && <p className="mt-0.5 text-xs text-muted">{field.help}</p>}
      <input
        id={id}
        type="text"
        onChange={(e) => {
          const val = e.target.value.trim();
          if (!val) {
            onValueChange(undefined);
            return;
          }
          // Parse comma-separated values into array for fields ending in "order" or "pages"
          if (field.name.includes("order") || field.name.includes("pages")) {
            const parts = val.split(",").map((p) => p.trim());
            onValueChange(parts.length === 1 ? parts[0] : parts);
          } else {
            onValueChange(val);
          }
        }}
        placeholder={field.help}
        className={fieldClass}
      />
    </div>
  );
}
