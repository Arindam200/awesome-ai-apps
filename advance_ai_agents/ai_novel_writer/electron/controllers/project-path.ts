import path from 'node:path'

export function sanitizeProjectName(name: string): string {
  const trimmed = name.trim()
  const baseName = trimmed.split(/[\\/]/).pop() || trimmed
  return baseName.replace(/[<>:"/\\|?*\x00-\x1F]/g, '_').trim() || '未命名项目'
}

export function resolveProjectDir(parentPath: string, projectName: string): string {
  return path.join(parentPath, sanitizeProjectName(projectName))
}
