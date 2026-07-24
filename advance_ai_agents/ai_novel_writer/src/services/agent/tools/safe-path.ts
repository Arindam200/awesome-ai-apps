/**
 * 路径安全校验工具
 *
 * 防止路径遍历攻击（../../ 等），确保所有文件操作都在项目根目录内。
 */

/**
 * 校验并 resolve 相对路径，确保不会越出项目根目录
 *
 * @param projectRoot 项目根目录（绝对路径）
 * @param relativePath 用户/LLM 提供的相对路径
 * @returns 安全的绝对路径，如果越界则返回 null
 */
export function safePath(projectRoot: string, relativePath: string): string | null {
  // 规范化路径分隔符
  const normalized = relativePath.replace(/\\/g, '/')

  // 拆分路径段并手动 resolve（不依赖 Node path 模块，因为运行在渲染进程）
  const segments = normalized.split('/')
  const resolvedSegments: string[] = []

  for (const seg of segments) {
    if (seg === '' || seg === '.') {
      continue
    }
    if (seg === '..') {
      if (resolvedSegments.length === 0) {
        // 已经越界
        return null
      }
      resolvedSegments.pop()
    } else {
      resolvedSegments.push(seg)
    }
  }

  const resolvedRelative = resolvedSegments.join('/')
  const fullPath = `${projectRoot}/${resolvedRelative}`

  // 最终检查：确保完整路径以项目根目录开头
  if (!fullPath.startsWith(projectRoot)) {
    return null
  }

  return fullPath
}

/**
 * 校验路径安全性的便捷包装
 * 如果不安全，直接返回 ToolResult 错误
 */
export function validatePath(
  projectRoot: string,
  relativePath: string,
): { valid: true; fullPath: string } | { valid: false; error: string } {
  if (!relativePath) {
    return { valid: false, error: '缺少文件路径参数' }
  }

  const result = safePath(projectRoot, relativePath)
  if (result === null) {
    return { valid: false, error: `路径越界：「${relativePath}」超出了项目目录范围。只能访问项目内的文件。` }
  }

  return { valid: true, fullPath: result }
}
