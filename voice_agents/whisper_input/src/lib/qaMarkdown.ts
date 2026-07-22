import { marked } from 'marked';

const SAFE_LINK_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:']);

function escapeHtml(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function decodeHtmlEntities(raw: string): string {
  return raw
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
}

function normalizeHref(href: string | null | undefined): string | null {
  if (!href) return null;
  const trimmed = href.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('#')) return trimmed;
  try {
    const url = new URL(trimmed, 'https://openless.local/');
    if (!SAFE_LINK_PROTOCOLS.has(url.protocol)) return null;
    return trimmed;
  } catch {
    return null;
  }
}

const QA_MARKDOWN_RENDERER = new marked.Renderer();
QA_MARKDOWN_RENDERER.html = (html: string) => escapeHtml(html);
QA_MARKDOWN_RENDERER.link = (href: string | null, title: string | null, text: string) => {
  const safeHref = normalizeHref(decodeHtmlEntities(href ?? ''));
  if (!safeHref) return `<span>${text}</span>`;
  const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
  return `<a href="${escapeHtml(safeHref)}"${titleAttr} target="_blank" rel="noreferrer noopener">${text}</a>`;
};
QA_MARKDOWN_RENDERER.image = (href: string | null, title: string | null, text: string) => {
  const safeHref = normalizeHref(decodeHtmlEntities(href ?? ''));
  if (!safeHref) return '';
  const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
  const alt = escapeHtml(text || '');
  return `<img src="${escapeHtml(safeHref)}" alt="${alt}"${titleAttr} loading="lazy" />`;
};

export function renderQaPlainText(raw: string): string {
  return `<pre>${escapeHtml(raw)}</pre>`;
}

export function renderQaMarkdown(markdown: string): string {
  // 保留 markdown 语义（尤其代码块），但把 raw HTML token 转义为纯文本，避免注入。
  return marked.parse(markdown, {
    async: false,
    gfm: true,
    breaks: true,
    renderer: QA_MARKDOWN_RENDERER,
  }) as string;
}
