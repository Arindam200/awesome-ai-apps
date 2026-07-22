/**
 * YAML Frontmatter 工具函数
 * — 用于草稿文件（含 --- 分隔的 YAML 元数据头）的解析与拼接
 *
 * 草稿文件格式：
 * ---
 * status: draft
 * version: 1
 * ...
 * ---
 *
 * 正文内容...
 */

/** Frontmatter 解析结果 */
export interface FrontmatterResult {
  /** YAML 头部完整字符串（含首尾 --- 及其后换行），如无则为空串 */
  frontmatter: string
  /** 去除 frontmatter 后的正文内容 */
  body: string
}

/**
 * 从文件内容中提取 frontmatter 与正文
 * @param content 完整文件内容
 */
export function extractFrontmatter(content: string): FrontmatterResult {
  const match = content.match(/^(---[\s\S]*?---\n\n?)/)
  if (!match) {
    return { frontmatter: '', body: content }
  }
  return {
    frontmatter: match[1],
    body: content.slice(match[1].length),
  }
}

/**
 * 将 frontmatter 与正文拼接为完整文件内容
 * @param frontmatter frontmatter 字符串（含首尾 ---）
 * @param body 正文内容
 */
export function mergeFrontmatterBody(frontmatter: string, body: string): string {
  if (!frontmatter) return body
  // 确保 frontmatter 以换行结尾再拼接正文
  const fm = frontmatter.endsWith('\n') ? frontmatter : frontmatter + '\n'
  return fm + body
}
