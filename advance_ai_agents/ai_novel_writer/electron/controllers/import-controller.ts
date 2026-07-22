import { ipcMain, dialog } from 'electron'
import fs from 'node:fs'
import path from 'node:path'

/**
 * 导入小说控制器 — 处理文件选择与章节拆分
 *
 * 拆章策略按优先级顺序尝试匹配：
 * 1. 中文标准格式："第X章 标题" / "第X章：标题"
 * 2. 英文标准格式："Chapter X: Title"
 * 3. Markdown 标题格式："# 第X章 标题"
 * 如果所有正则均不命中，则将整个文件视为单章。
 */

// ===== 拆章正则池 =====

/** 中文"第X章"格式（支持中文数字和阿拉伯数字，冒号可有可无） */
const RE_CN_CHAPTER = /^第[一二三四五六七八九十百千零\d]+章[\s：:·—-]*(.*)/

/** 英文 "Chapter X" 格式 */
const RE_EN_CHAPTER = /^Chapter\s+(\d+)[\s：:·—-]*(.*)/i

/** Markdown 标题格式："# 第X章" 或 "## Chapter X" */
const RE_MD_HEADING = /^#{1,3}\s+(?:第[一二三四五六七八九十百千零\d]+章|Chapter\s+\d+)[\s：:·—-]*(.*)/i

/** 所有候选正则 */
const CHAPTER_PATTERNS = [RE_CN_CHAPTER, RE_EN_CHAPTER, RE_MD_HEADING]

/** 中文数字到阿拉伯数字的映射 */
function chineseNumToArabic(str: string): number {
  const map: Record<string, number> = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
    '十': 10, '百': 100, '千': 1000,
  }

  // 纯阿拉伯数字
  const n = parseInt(str)
  if (!isNaN(n)) return n

  // 中文数字解析（支持"一百二十三"等简单组合）
  let result = 0
  let current = 0
  for (const ch of str) {
    const val = map[ch]
    if (val === undefined) continue
    if (val >= 10) {
      if (current === 0) current = 1
      current *= val
      result += current
      current = 0
    } else {
      current = val
    }
  }
  return result + current
}

/** 从章节标题行提取章节号 */
function extractChapterNumber(line: string): number {
  // 尝试从"第X章"格式提取
  const cnMatch = line.match(/第([一二三四五六七八九十百千零\d]+)章/)
  if (cnMatch) return chineseNumToArabic(cnMatch[1])

  // 尝试从"Chapter X"格式提取
  const enMatch = line.match(/Chapter\s+(\d+)/i)
  if (enMatch) return parseInt(enMatch[1])

  return 0
}

/** 检测一行是否是章节标题 */
function isChapterHeading(line: string): boolean {
  const trimmed = line.trim()
  return CHAPTER_PATTERNS.some(re => re.test(trimmed))
}

/** 从章节标题行提取标题文字（去掉"第X章"前缀） */
function extractTitle(line: string): string {
  const trimmed = line.trim()
  for (const re of CHAPTER_PATTERNS) {
    const match = trimmed.match(re)
    if (match) {
      // 取最后一个捕获组（标题部分）
      const title = match[match.length - 1]?.trim()
      if (title) return title
      // 如果标题为空，返回完整行
      return trimmed
    }
  }
  return trimmed
}

interface ParsedChapter {
  number: number
  title: string
  content: string
  wordCount: number
}

/** 将单个文件内容拆分为章节数组 */
function splitSingleFileContent(content: string): ParsedChapter[] {
  const lines = content.split('\n')
  const chapters: ParsedChapter[] = []
  let currentChapter: { headerLine: string; lines: string[] } | null = null
  let autoNumber = 0

  for (const line of lines) {
    if (isChapterHeading(line)) {
      // 保存上一个章节
      if (currentChapter) {
        autoNumber++
        const num = extractChapterNumber(currentChapter.headerLine) || autoNumber
        const text = currentChapter.lines.join('\n').trim()
        if (text.length > 0) {
          chapters.push({
            number: num,
            title: extractTitle(currentChapter.headerLine),
            content: text,
            wordCount: text.length,
          })
        }
      }
      // 开始新章节
      currentChapter = { headerLine: line, lines: [] }
    } else if (currentChapter) {
      currentChapter.lines.push(line)
    } else {
      // 在第一个章节标题之前的内容 → 创建前言/序章
      if (!currentChapter) {
        currentChapter = { headerLine: line, lines: [] }
      }
    }
  }

  // 保存最后一个章节
  if (currentChapter) {
    autoNumber++
    const num = extractChapterNumber(currentChapter.headerLine) || autoNumber
    const text = currentChapter.lines.join('\n').trim()
    if (text.length > 0) {
      chapters.push({
        number: num,
        title: extractTitle(currentChapter.headerLine),
        content: text,
        wordCount: text.length,
      })
    }
  }

  return chapters
}

/** 如果内容中没有匹配到任何章节标题，则整文件视为一章 */
function hasChapterHeadings(content: string): boolean {
  const lines = content.split('\n')
  return lines.some(line => isChapterHeading(line))
}

export function registerImportController() {
  // ===== 文件选择对话框 =====
  ipcMain.handle('dialog:select-novel-files', async () => {
    const result = await dialog.showOpenDialog({
      title: '选择要导入的小说文件',
      filters: [
        { name: '小说文本', extensions: ['txt', 'md', 'text'] },
        { name: '所有文件', extensions: ['*'] },
      ],
      properties: ['openFile', 'multiSelections'],
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths
  })

  // ===== 读取并拆分章节 =====
  ipcMain.handle('import:split-chapters', async (_event, filePaths: string[]) => {
    try {
      const allChapters: ParsedChapter[] = []

      if (filePaths.length === 1) {
        // ===== 单文件模式 =====
        const filePath = filePaths[0]
        const content = fs.readFileSync(filePath, 'utf-8')

        if (hasChapterHeadings(content)) {
          // 文件内含章节标题 → 正则拆章
          const chapters = splitSingleFileContent(content)
          allChapters.push(...chapters)
        } else {
          // 无章节标题 → 整文件视为一章
          allChapters.push({
            number: 1,
            title: path.basename(filePath, path.extname(filePath)),
            content: content.trim(),
            wordCount: content.trim().length,
          })
        }
      } else {
        // ===== 多文件模式 =====
        // 按文件名自然排序
        const sorted = [...filePaths].sort((a, b) => {
          const nameA = path.basename(a)
          const nameB = path.basename(b)
          return nameA.localeCompare(nameB, 'zh-CN', { numeric: true })
        })

        for (let i = 0; i < sorted.length; i++) {
          const filePath = sorted[i]
          const content = fs.readFileSync(filePath, 'utf-8').trim()
          if (!content) continue

          // 尝试从文件内容中检测章节标题
          if (hasChapterHeadings(content)) {
            // 文件内含多章 → 拆分
            const chapters = splitSingleFileContent(content)
            allChapters.push(...chapters)
          } else {
            // 文件内无章节标题 → 整文件视为一章
            const fileName = path.basename(filePath, path.extname(filePath))
            const num = extractChapterNumber(fileName) || (allChapters.length + 1)
            allChapters.push({
              number: num,
              title: fileName,
              content,
              wordCount: content.length,
            })
          }
        }
      }

      // 去重排序：按章节号排序，重复章号保留后者
      const chapterMap = new Map<number, ParsedChapter>()
      for (const ch of allChapters) {
        chapterMap.set(ch.number, ch)
      }
      const finalChapters = Array.from(chapterMap.values())
        .sort((a, b) => a.number - b.number)

      // 重新编号（确保从1开始连续）
      const renumbered = finalChapters.map((ch, idx) => ({
        ...ch,
        number: idx + 1,
      }))

      const totalWords = renumbered.reduce((sum, ch) => sum + ch.wordCount, 0)

      return {
        success: true,
        chapters: renumbered,
        totalWords,
      }
    } catch (error) {
      return {
        success: false,
        chapters: [],
        totalWords: 0,
        error: String(error),
      }
    }
  })
}
