import type { ReactNode } from "react";

type MarkdownArticleVariant = "app" | "print";

function markdownCells(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s)]+|`[^`]+`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={`${part}-${index}`} className="rounded bg-panel2 px-1 py-0.5 font-mono text-[0.92em] text-text">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (/^https?:\/\//.test(part)) {
      return (
        <a key={`${part}-${index}`} href={part} className="break-all text-blue underline decoration-blue/40 underline-offset-2">
          {part}
        </a>
      );
    }
    return part;
  });
}

const variantClasses = {
  app: {
    root: "space-y-5",
    h1: "text-3xl font-semibold leading-10 text-text",
    h2: "border-t border-line pt-6 text-xl font-semibold leading-8 text-text",
    h3: "text-base font-semibold leading-7 text-text",
    p: "text-sm leading-7 text-muted",
    list: "space-y-2 pl-5 text-sm leading-7 text-muted",
    ordered: "space-y-3 pl-5 text-sm leading-7 text-muted",
    tableWrap: "thin-scroll overflow-x-auto",
    table: "w-full min-w-[520px] border-collapse text-left text-sm",
    th: "border border-line bg-panel2 px-3 py-2 font-semibold text-text",
    td: "border border-line px-3 py-2 align-top text-muted"
  },
  print: {
    root: "space-y-6 text-[#1f2933]",
    h1: "mb-2 text-[34px] font-semibold leading-tight tracking-normal text-[#111827]",
    h2: "mt-9 border-t border-[#d8ddd6] pt-5 text-[22px] font-semibold leading-8 text-[#111827]",
    h3: "mt-5 text-[17px] font-semibold leading-7 text-[#111827]",
    p: "text-[14.5px] leading-7 text-[#37423e]",
    list: "space-y-2 pl-6 text-[14.5px] leading-7 text-[#37423e]",
    ordered: "space-y-3 pl-6 text-[14.5px] leading-7 text-[#37423e]",
    tableWrap: "overflow-x-auto rounded-lg border border-[#d8ddd6]",
    table: "w-full min-w-[520px] border-collapse text-left text-[13.5px]",
    th: "border border-[#d8ddd6] bg-[#f2f1ec] px-3 py-2 font-semibold text-[#111827]",
    td: "border border-[#d8ddd6] px-3 py-2 align-top leading-6 text-[#37423e]"
  }
} satisfies Record<MarkdownArticleVariant, Record<string, string>>;

export function MarkdownArticle({ markdown, variant = "app" }: { markdown: string; variant?: MarkdownArticleVariant }) {
  const classes = variantClasses[variant];
  const lines = markdown.split(/\r?\n/);
  const nodes: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index]?.trimEnd() ?? "";
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (line.startsWith("# ")) {
      nodes.push(
        <h1 key={index} className={classes.h1}>
          {line.replace(/^#\s+/, "")}
        </h1>
      );
      index += 1;
      continue;
    }

    if (line.startsWith("## ")) {
      nodes.push(
        <h2 key={index} className={classes.h2}>
          {line.replace(/^##\s+/, "")}
        </h2>
      );
      index += 1;
      continue;
    }

    if (line.startsWith("### ")) {
      nodes.push(
        <h3 key={index} className={classes.h3}>
          {line.replace(/^###\s+/, "")}
        </h3>
      );
      index += 1;
      continue;
    }

    if (line.trim().startsWith("|")) {
      const tableLines: string[] = [];
      while (index < lines.length && lines[index]?.trim().startsWith("|")) {
        tableLines.push(lines[index]);
        index += 1;
      }
      const [headerLine, separatorLine, ...bodyLines] = tableLines;
      const headers = markdownCells(headerLine ?? "");
      const hasSeparator = Boolean(separatorLine?.includes("---"));
      const rows = (hasSeparator ? bodyLines : tableLines.slice(1)).map(markdownCells);
      nodes.push(
        <div key={index} className={classes.tableWrap}>
          <table className={classes.table}>
            <thead>
              <tr>
                {headers.map((header) => (
                  <th key={header} className={classes.th}>
                    {header || "Field"}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`${row.join("-")}-${rowIndex}`}>
                  {headers.map((header, cellIndex) => (
                    <td key={`${header}-${cellIndex}`} className={classes.td}>
                      {renderInline(row[cellIndex] || "Not available")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index]?.trim() ?? "")) {
        items.push((lines[index] ?? "").trim().replace(/^[-*]\s+/, ""));
        index += 1;
      }
      nodes.push(
        <ul key={index} className={classes.list}>
          {items.map((item) => (
            <li key={item} className="list-disc">
              {renderInline(item)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && (/^\d+\.\s+/.test(lines[index]?.trim() ?? "") || /^\s+Source:/.test(lines[index] ?? ""))) {
        const current = lines[index] ?? "";
        if (/^\d+\.\s+/.test(current.trim())) {
          items.push(current.trim().replace(/^\d+\.\s+/, ""));
        } else if (items.length > 0) {
          items[items.length - 1] = `${items[items.length - 1]}\n${current.trim()}`;
        }
        index += 1;
      }
      nodes.push(
        <ol key={index} className={classes.ordered}>
          {items.map((item) => (
            <li key={item} className="list-decimal whitespace-pre-line">
              {renderInline(item)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    const paragraph: string[] = [];
    while (
      index < lines.length &&
      lines[index]?.trim() &&
      !/^(#|\||\* |\d+\.)/.test(lines[index]?.trim() ?? "")
    ) {
      paragraph.push(lines[index]?.trim() ?? "");
      index += 1;
    }
    nodes.push(
      <p key={index} className={classes.p}>
        {renderInline(paragraph.join(" "))}
      </p>
    );
  }

  return <div className={classes.root}>{nodes}</div>;
}
