// Generated simulations run with no network at all: a CSP that only allows inline code,
// a sandboxed iframe in the app (no same-origin), and blocked requests in Playwright.
export const CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:";

// The policy is inserted before <html>, right after any doctype. An HTML parser that meets a
// <meta> there opens <head> for it, so the policy applies wherever the page's own <head> is,
// even when the page is cut off or starts with stray text (which is dropped).
export function lockDown(html: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${CSP}">`;
  const start = html.search(/<!doctype|<html|<head|<body|<svg/i);
  const doc = start > 0 ? html.slice(start) : html;
  const doctype = doc.match(/^\s*<!doctype[^>]*>/i)?.[0];
  if (doctype) return `${doctype}${meta}${doc.slice(doctype.length)}`;
  if (start === -1) return `<!doctype html>${meta}<body>${doc}</body>`;
  return `<!doctype html>${meta}${doc}`;
}
