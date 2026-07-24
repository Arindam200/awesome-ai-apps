/**
 * 草稿状态共享常量与类型
 * — 统一 Sidebar、DraftEditor 等多处的状态标签和颜色显示，避免重复定义和不一致
 */

/** 草稿状态类型 */
export type DraftStatus = 'draft' | 'revised' | 'reviewed' | 'finalized' | 'archived'


/** 草稿状态 → 中文标签 */
export const DRAFT_STATUS_LABEL: Record<string, string> = {
  draft:     '草稿',
  revised:   '已修稿',
  reviewed:  '已审稿',
  finalized: '已定稿',
  archived:  '已归档',
}

/** 草稿状态 → 显示颜色（使用 CSS 变量保证主题适配） */
export const DRAFT_STATUS_COLOR: Record<string, string> = {
  draft:     'var(--color-text-muted)',
  revised:   '#60a5fa',           /* 蓝色 — 表示已有改进 */
  reviewed:  '#a78bfa',           /* 紫色 — 表示已审核 */
  finalized: 'var(--color-success)',
  archived:  'var(--color-text-muted)',
}
