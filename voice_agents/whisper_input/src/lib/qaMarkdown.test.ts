import { renderQaMarkdown } from './qaMarkdown';

function assertIncludes(text: string, expected: string, name: string) {
  if (!text.includes(expected)) {
    throw new Error(`${name}: expected to include "${expected}", got "${text}"`);
  }
}

function assertNotIncludes(text: string, expected: string, name: string) {
  if (text.includes(expected)) {
    throw new Error(`${name}: expected not to include "${expected}", got "${text}"`);
  }
}

const htmlEscaped = renderQaMarkdown('<img src=x onerror=alert(1)><script>alert(1)</script>');
assertIncludes(htmlEscaped, '&lt;img src=x onerror=alert(1)&gt;', 'raw html should be escaped');
assertNotIncludes(htmlEscaped, '<script>', 'script tag should not be rendered');
assertNotIncludes(htmlEscaped, '<img src=x onerror=alert(1)>', 'raw html img should not become live dom tag');

const badHref = renderQaMarkdown('[xss](javascript:alert(1))');
assertNotIncludes(badHref, 'href="javascript:alert(1)"', 'javascript href should be dropped');

const goodMarkdown = renderQaMarkdown('**bold**\n\n- a\n- b\n\n`code`\n\n[ok](https://example.com)');
assertIncludes(goodMarkdown, '<strong>bold</strong>', 'bold markdown should render');
assertIncludes(goodMarkdown, '<li>a</li>', 'list markdown should render');
assertIncludes(goodMarkdown, '<code>code</code>', 'code markdown should render');
assertIncludes(goodMarkdown, 'href="https://example.com"', 'safe link should render');

const safeQueryLink = renderQaMarkdown('[ok](https://example.com?a=1&b=2)');
assertIncludes(safeQueryLink, 'href="https://example.com?a=1&amp;b=2"', 'safe query link should keep a single escaped ampersand');

const codeSnippet = renderQaMarkdown('`<div class=\"x\">`');
assertIncludes(codeSnippet, '&lt;div class=&quot;x&quot;&gt;', 'inline code should stay single-escaped');
assertNotIncludes(codeSnippet, '&amp;lt;', 'inline code should not be double-escaped');
