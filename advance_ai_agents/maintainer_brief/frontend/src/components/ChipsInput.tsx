"use client";

import { useState } from "react";
import { X } from "lucide-react";

export default function ChipsInput({
  values,
  onChange,
  placeholder,
  type = "text",
}: {
  values: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  type?: string;
}) {
  const [draft, setDraft] = useState("");

  const add = () => {
    const v = draft.trim();
    if (v && !values.includes(v)) onChange([...values, v]);
    setDraft("");
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-[6px] border border-line bg-surface px-2 py-1.5 transition-colors focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15">
      {values.map((v) => (
        <span
          key={v}
          className="inline-flex items-center gap-1 rounded-[4px] bg-primary-soft px-2 py-0.5 text-xs font-medium text-primary"
        >
          {v}
          <button
            type="button"
            onClick={() => onChange(values.filter((x) => x !== v))}
            className="text-primary/50 transition-colors hover:text-primary"
          >
            <X size={12} strokeWidth={2.5} />
          </button>
        </span>
      ))}
      <input
        type={type}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            add();
          } else if (e.key === "Backspace" && !draft && values.length) {
            onChange(values.slice(0, -1));
          }
        }}
        onBlur={add}
        placeholder={values.length ? "" : placeholder}
        className="min-w-[120px] flex-1 bg-transparent px-1 py-0.5 text-sm text-ink placeholder:text-faint outline-none"
      />
    </div>
  );
}
