import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function source(file: string) {
  return readFileSync(resolve(process.cwd(), file), 'utf8')
}

describe('generated content deletion affordances', () => {
  it('exposes visible all-generated-content clearing from the project tree', () => {
    const projectTree = source('src/components/panels/sidebar/ProjectTree.tsx')

    expect(projectTree).toContain('清除全部')
    expect(projectTree).toContain('清除项目生成内容')
  })

  it('supports deleting one blueprint and clearing all blueprints through persisted IPC', () => {
    const chapterCards = source('src/components/editor/ChapterCardEditor.tsx')
    const dbController = source('electron/controllers/db-controller.ts')
    const ipcChannels = source('src/shared/ipc-channels.ts')

    expect(chapterCards).toContain('删除此章')
    expect(chapterCards).toContain('清空全部蓝图')
    expect(chapterCards).toContain('db:blueprint-delete')
    expect(dbController).toContain("'db:blueprint-delete'")
    expect(ipcChannels).toContain("'db:blueprint-delete'")
  })

  it('supports deleting generated drafts and finalized manuscript chapters through persisted IPC', () => {
    const draftBox = source('src/components/panels/sidebar/DraftBoxGroup.tsx')
    const manuscript = source('src/components/panels/sidebar/ManuscriptGroup.tsx')
    const dbController = source('electron/controllers/db-controller.ts')
    const ipcChannels = source('src/shared/ipc-channels.ts')

    expect(draftBox).toContain('删除这一稿')
    expect(draftBox).toContain('db:draft-delete')
    expect(manuscript).toContain('删除正文')
    expect(manuscript).toContain('db:draft-delete')
    expect(dbController).toContain("'db:draft-delete'")
    expect(ipcChannels).toContain("'db:draft-delete'")
  })

  it('supports clearing the entire knowledge base from the knowledge page', () => {
    const knowledgePage = source('src/components/pages/KnowledgeOverview.tsx')
    const knowledgeService = source('src/services/knowledge-service.ts')
    const kbController = source('electron/controllers/kb-controller.ts')
    const ipcChannels = source('src/shared/ipc-channels.ts')

    expect(knowledgePage).toContain('清空知识库')
    expect(knowledgePage).toContain('clearKnowledgeBase')
    expect(knowledgeService).toContain('kb:clear-all')
    expect(kbController).toContain("'kb:clear-all'")
    expect(ipcChannels).toContain("'kb:clear-all'")
  })

  it('supports deleting recent and current projects through persisted IPC', () => {
    const homeSidebar = source('src/components/panels/sidebar/HomeSidebarPanel.tsx')
    const projectStore = source('src/stores/project-store.ts')
    const projectController = source('electron/controllers/project-controller.ts')
    const ipcChannels = source('src/shared/ipc-channels.ts')

    expect(homeSidebar).toContain('删除项目')
    expect(projectStore).toContain('deleteProject')
    expect(projectController).toContain("'project:delete'")
    expect(ipcChannels).toContain("'project:delete'")
  })
})
