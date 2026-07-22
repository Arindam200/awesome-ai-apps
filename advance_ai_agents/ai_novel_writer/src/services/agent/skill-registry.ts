/**
 * Skill 注册中心
 *
 * 管理所有可用的 Skill（基于 SKILL.md 的模块化知识包）。
 * 支持：
 * - 内置 Skill（随 Vela 发布的预设 Skill）
 * - 用户 Skill（用户放在 ~/.vela/skills/ 下的自定义 Skill）
 * - 项目 Skill（放在项目的 .vela/skills/ 下的项目级 Skill）
 *
 * Skill 格式兼容 Cursor 的 SKILL.md 生态。
 */

import { ipc } from '../ipc-client'
import { useProjectStore } from '../../stores/project-store'
import { toolRegistry, type AgentTool } from './tool-registry'

// ===== 类型定义 =====

/** Skill 来源 */
export type SkillSource = 'builtin' | 'user' | 'project'

/** Skill 元数据（从 SKILL.md frontmatter 解析） */
export interface SkillMetadata {
  /** Skill 唯一名称 */
  name: string
  /** 显示名称 */
  displayName?: string
  /** 功能描述 */
  description: string
  /** 使用场景（用于 Agent 自动匹配） */
  whenToUse?: string
  /** 版本 */
  version?: string
  /** 允许的工具列表（白名单） */
  allowedTools?: string[]
  /** 参数提示 */
  argumentHint?: string
  /** 是否可由模型自动调用 */
  userInvocable?: boolean
}

/** 加载后的 Skill */
export interface LoadedSkill {
  /** 元数据 */
  metadata: SkillMetadata
  /** Skill 内容（Markdown 提示词） */
  content: string
  /** 来源 */
  source: SkillSource
  /** 文件所在目录 */
  baseDir: string
  /** SKILL.md 文件路径 */
  filePath: string
}

// ===== Skill Registry =====

class SkillRegistryImpl {
  private skills: Map<string, LoadedSkill> = new Map()

  /** 注册一个 Skill */
  register(skill: LoadedSkill): void {
    this.skills.set(skill.metadata.name, skill)
  }

  /** 查找 Skill */
  get(name: string): LoadedSkill | undefined {
    return this.skills.get(name)
  }

  /** 列出所有 Skill */
  listAll(): LoadedSkill[] {
    return Array.from(this.skills.values())
  }

  /** 按来源列出 */
  listBySource(source: SkillSource): LoadedSkill[] {
    return this.listAll().filter(s => s.source === source)
  }

  /** Skill 数量 */
  get size(): number {
    return this.skills.size
  }

  /** 清空 */
  clear(): void {
    this.skills.clear()
  }

  /**
   * 从目录加载 Skills
   *
   * 扫描指定目录下的 skill-name/SKILL.md 格式
   */
  async loadFromDirectory(dir: string, source: SkillSource): Promise<number> {
    let count = 0
    try {
      const entries = await ipc.invoke('fs:list-dir', dir)
      for (const entry of entries) {
        if (!entry.isDir) continue

        const skillFile = `${entry.path}/SKILL.md`
        try {
          const exists = await ipc.invoke('fs:check-exists', skillFile)
          if (!exists) continue

          const result = await ipc.invoke('fs:read-file', skillFile)
          if (!result.success) continue

          const skill = parseSkillMd(result.content, entry.name, source, entry.path, skillFile)
          if (skill) {
            this.register(skill)
            count++
          }
        } catch {
          // 单个 Skill 加载失败不影响整体
        }
      }
    } catch {
      // 目录不存在等情况，静默处理
    }
    return count
  }

  /**
   * 加载所有 Skill（内置 + 用户 + 项目）
   */
  async loadAll(): Promise<void> {
    this.clear()

    // 注册内置 Skill
    registerBuiltinSkills(this)

    // 加载用户 Skill（~/.vela/skills/）
    try {
      const velaHome = await ipc.invoke('config:get-vela-home')
      const userSkillsDir = `${velaHome}/skills`
      const userCount = await this.loadFromDirectory(userSkillsDir, 'user')
      if (userCount > 0) {
        console.log(`[Skills] 加载了 ${userCount} 个用户 Skill`)
      }
    } catch {
      // 静默处理
    }

    // 加载项目 Skill（项目/.vela/skills/）
    const project = useProjectStore.getState().currentProject
    if (project) {
      const projectSkillsDir = `${project.path}/.vela/skills`
      const projectCount = await this.loadFromDirectory(projectSkillsDir, 'project')
      if (projectCount > 0) {
        console.log(`[Skills] 加载了 ${projectCount} 个项目 Skill`)
      }
    }

    // 将所有 Skill 注册为 Agent Tool
    this.registerToToolRegistry()

    console.log(`[Skills] 共加载 ${this.size} 个 Skill`)
  }

  /**
   * 将 Skill 注册为 Agent Tool
   */
  private registerToToolRegistry(): void {
    // 先清理旧的 Skill Tool
    toolRegistry.unregisterBySource('skill')

    for (const skill of this.listAll()) {
      const agentTool: AgentTool = {
        name: `skill__${skill.metadata.name}`,
        description: skill.metadata.description + (skill.metadata.whenToUse ? ` — ${skill.metadata.whenToUse}` : ''),
        source: 'skill',
        inputSchema: {
          type: 'object',
          properties: {
            args: {
              type: 'string',
              description: skill.metadata.argumentHint ?? '可选的参数',
            },
          },
        },
        requiresConfirmation: false,
        isReadOnly: true,
        userFacingName: skill.metadata.displayName ?? skill.metadata.name,
        execute: async (toolArgs) => {
          const userArgs = (toolArgs.args as string) ?? ''
          // 变量替换
          let content = skill.content
          if (userArgs) {
            content = content.replace(/\$\{args\}/g, userArgs)
            content = content.replace(/\$1/g, userArgs)
          }
          content = content.replace(/\$\{SKILL_DIR\}/g, skill.baseDir)

          return {
            success: true,
            content: `[Skill: ${skill.metadata.displayName ?? skill.metadata.name}]\n\n${content}`,
          }
        },
      }
      toolRegistry.register(agentTool)
    }
  }
}

/** 全局 Skill 注册中心 */
export const skillRegistry = new SkillRegistryImpl()

// ===== SKILL.md 解析 =====

/**
 * 解析 SKILL.md 文件内容
 *
 * 格式：
 * ```
 * ---
 * name: skill-name
 * description: 功能描述
 * when_to_use: 什么时候使用
 * allowed-tools: [read_file, search_knowledge]
 * ---
 *
 * # Skill 提示词内容
 * ...
 * ```
 */
function parseSkillMd(
  raw: string,
  fallbackName: string,
  source: SkillSource,
  baseDir: string,
  filePath: string,
): LoadedSkill | null {
  // 解析 frontmatter
  const fmMatch = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n/)
  const frontmatter: Record<string, unknown> = {}
  let content = raw

  if (fmMatch) {
    const fmText = fmMatch[1]
    content = raw.slice(fmMatch[0].length)

    // 简单的 YAML 解析（支持 key: value 和 key: [items]）
    for (const line of fmText.split('\n')) {
      const kvMatch = line.match(/^\s*([^:]+):\s*(.*)$/)
      if (!kvMatch) continue
      const key = kvMatch[1].trim()
      let val: unknown = kvMatch[2].trim()

      // 解析数组 [a, b, c]
      if (typeof val === 'string' && val.startsWith('[') && val.endsWith(']')) {
        val = val.slice(1, -1).split(',').map(s => s.trim()).filter(Boolean)
      }
      // 解析布尔值
      if (val === 'true') val = true
      if (val === 'false') val = false

      frontmatter[key] = val
    }
  }

  const metadata: SkillMetadata = {
    name: (frontmatter['name'] as string) || fallbackName,
    displayName: frontmatter['display_name'] as string,
    description: (frontmatter['description'] as string) || `Skill: ${fallbackName}`,
    whenToUse: frontmatter['when_to_use'] as string,
    version: frontmatter['version'] as string,
    allowedTools: frontmatter['allowed-tools'] as string[],
    argumentHint: frontmatter['argument-hint'] as string,
    userInvocable: frontmatter['user-invocable'] !== false,
  }

  return {
    metadata,
    content: content.trim(),
    source,
    baseDir,
    filePath,
  }
}

// ===== 内置 Skills =====

function registerBuiltinSkills(registry: SkillRegistryImpl): void {
  const builtins: Array<{ metadata: SkillMetadata; content: string }> = [
    {
      metadata: {
        name: 'review-chapter',
        displayName: '章节审阅',
        description: '对指定章节进行全面的质量审阅，包括剧情逻辑、角色一致性、节奏感、伏笔呼应等多个维度。',
        whenToUse: '用户要求审阅、检查、评估某个章节时',
      },
      content: `# 章节审阅

请对目标章节进行专业的小说审阅。依次检查以下维度：

## 1. 剧情逻辑
- 情节是否连贯，有无逻辑矛盾
- 因果关系是否成立

## 2. 角色一致性
- 角色行为是否符合既定性格
- 对话风格是否一致

## 3. 节奏感
- 张弛是否有度
- 是否有不必要的拖沓或过于仓促的转折

## 4. 伏笔与呼应
- 已有伏笔是否得到了回应
- 新埋的伏笔是否自然

## 5. 文笔与风格
- 描写是否生动
- 是否符合整体文风设定

请先使用 read_drafts 工具读取目标章节，再使用 read_architecture 读取故事架构进行对比评估。
输出格式：每个维度评分（1-5星）+ 详细说明 + 修改建议。`,
    },
    {
      metadata: {
        name: 'brainstorm',
        displayName: '脑暴创意',
        description: '针对指定话题进行创意脑暴，生成多个创意方向和灵感。',
        whenToUse: '用户要求头脑风暴、找灵感、想创意时',
      },
      content: `# 创意脑暴

请围绕用户给出的话题进行专业的创意脑暴。

## 输出格式
为每个创意方向提供：
1. **创意概念**（一句话）
2. **详细展开**（100-200 字）
3. **可行性评估**（高/中/低）
4. **与已有剧情的融合度**

请先使用 read_architecture 和 read_project_state 了解项目背景，确保创意与现有设定不矛盾。
至少提供 5 个不同方向的创意。`,
    },
    {
      metadata: {
        name: 'character-analysis',
        displayName: '角色分析',
        description: '深入分析指定角色的性格、动机、角色弧、人物关系等。',
        whenToUse: '用户想深入了解或调整角色设定时',
      },
      content: `# 角色深度分析

请对目标角色进行全方位的深度分析。

## 分析维度
1. **核心性格特质** — MBTI、大五人格倾向
2. **深层动机** — 驱动角色行动的核心诉求
3. **角色弧预测** — 基于当前设定推演角色成长轨迹
4. **关系网络** — 与其他角色的关系图谱
5. **冲突点** — 角色面临的核心矛盾和困境
6. **独特标识** — 口头禅、习惯动作、标志性特征

请先使用 read_characters 读取角色卡，以及 read_architecture 了解故事结构。`,
    },
    {
      metadata: {
        name: 'continuity-check',
        displayName: '连续性检查',
        description: '检查小说中的设定一致性和连续性问题，发现矛盾和遗漏。',
        whenToUse: '用户想检查设定有没有矛盾、是否有不一致的地方时',
      },
      content: `# 连续性与一致性检查

请对项目进行全面的连续性检查。

## 检查项
1. **时间线一致性** — 事件发生顺序是否合理
2. **地理一致性** — 地点描述是否前后一致
3. **角色状态** — 角色的伤病、装备、能力等是否正确追踪
4. **设定遵守** — 是否与世界观设定产生矛盾
5. **伏笔追踪** — 哪些伏笔已回收，哪些待回收

请使用 list_chapters 了解进度，使用 read_architecture 获取设定，逐章检查关键节点。
输出为表格形式，标注问题严重程度（🔴严重 / 🟡注意 / 🟢正常）。`,
    },
    {
      metadata: {
        name: 'writing-coach',
        displayName: '写作教练',
        description: '提供专业的写作技巧指导和文笔改善建议。',
        whenToUse: '用户想提高写作水平、求教写作技巧时',
      },
      content: `# 写作教练

作为专业的写作教练，为用户提供针对性的指导。

## 指导范围
- 叙述技巧（视角运用、时间线处理）
- 描写技法（环境渲染、人物刻画）
- 对话写作（个性化对话、潜台词运用）
- 节奏控制（场景切换、留白技巧）
- 悬念设置（钩子、反转、暗线）

请先使用 read_project_state 了解项目的写作风格设定，
再根据用户的具体问题提供定制化建议，并附上示例对比。`,
    },
  ]

  for (const { metadata, content } of builtins) {
    registry.register({
      metadata,
      content,
      source: 'builtin',
      baseDir: '',
      filePath: `builtin://${metadata.name}`,
    })
  }
}
