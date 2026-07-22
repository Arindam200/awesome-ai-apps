import fs from 'node:fs'
import path from 'node:path'

import { getCurrentProjectPath, getProjectDb } from '../database'

export type ProjectClearScope = 'creativeFields' | 'blueprints' | 'generatedText'

export interface ProjectClearOptions {
    creativeFields?: boolean
    blueprints?: boolean
    generatedText?: boolean
}

export interface ProjectClearResult {
    cleared: ProjectClearScope[]
    physicalFilesDeleted: number
}

interface MovedFile {
    from: string
    to: string
}

const FINALIZED_CHAPTER_FILE_RE = /^第\d+章(?: .*)?\.txt$/u

function listGeneratedChapterFiles(projectPath: string): string[] {
    if (!fs.existsSync(projectPath)) return []
    return fs.readdirSync(projectPath, { withFileTypes: true })
        .filter(entry => entry.isFile() && FINALIZED_CHAPTER_FILE_RE.test(entry.name))
        .map(entry => path.join(projectPath, entry.name))
}

function moveGeneratedFilesToTrash(projectPath: string): MovedFile[] {
    const files = listGeneratedChapterFiles(projectPath)
    if (files.length === 0) return []

    const trashDir = path.join(
        projectPath,
        '.vela',
        'trash',
        `clear-${new Date().toISOString().replace(/[:.]/g, '-')}`,
    )
    fs.mkdirSync(trashDir, { recursive: true })

    const moved: MovedFile[] = []
    try {
        for (const file of files) {
            const target = path.join(trashDir, path.basename(file))
            fs.renameSync(file, target)
            moved.push({ from: file, to: target })
        }
        return moved
    } catch (error) {
        restoreMovedFiles(moved)
        throw error
    }
}

function restoreMovedFiles(moved: MovedFile[]): void {
    for (const item of [...moved].reverse()) {
        if (fs.existsSync(item.to) && !fs.existsSync(item.from)) {
            fs.renameSync(item.to, item.from)
        }
    }
}

function removeMovedFiles(moved: MovedFile[]): void {
    const dirs = new Set<string>()
    for (const item of moved) {
        dirs.add(path.dirname(item.to))
    }

    for (const dir of dirs) {
        fs.rmSync(dir, { recursive: true, force: true })
    }
}

export class ProjectClearRepository {
    static clearGeneratedData(options: ProjectClearOptions): ProjectClearResult {
        const db = getProjectDb()
        if (!db) throw new Error('项目数据库未打开')

        const projectPath = getCurrentProjectPath()
        if (options.generatedText && !projectPath) throw new Error('项目路径未初始化')

        const movedFiles = options.generatedText && projectPath
            ? moveGeneratedFilesToTrash(projectPath)
            : []
        const cleared: ProjectClearScope[] = []

        try {
            const tx = db.transaction(() => {
                if (options.generatedText) {
                    db.prepare('DELETE FROM post_process_steps').run()
                    db.prepare('DELETE FROM post_process_runs').run()
                    db.prepare('DELETE FROM reviews').run()
                    db.prepare('DELETE FROM revisions').run()
                    db.prepare('DELETE FROM drafts').run()
                    db.prepare('DELETE FROM contents').run()
                    db.prepare('DELETE FROM summary_snapshots').run()
                    cleared.push('generatedText')
                }

                if (options.blueprints) {
                    db.prepare('DELETE FROM blueprints').run()
                    cleared.push('blueprints')
                }

                if (options.creativeFields) {
                    db.prepare(`
                        UPDATE project_core
                        SET writing_style = '',
                            reference_works = '',
                            global_guidance = '',
                            golden_finger = '',
                            premise = '',
                            worldbuilding = '',
                            characters_arch = '',
                            synopsis = '',
                            character_states = '',
                            updated_at = datetime('now')
                        WHERE id = 'main'
                    `).run()
                    cleared.push('creativeFields')
                }
            })

            tx()
            removeMovedFiles(movedFiles)
            return { cleared, physicalFilesDeleted: movedFiles.length }
        } catch (error) {
            restoreMovedFiles(movedFiles)
            throw error
        }
    }
}
