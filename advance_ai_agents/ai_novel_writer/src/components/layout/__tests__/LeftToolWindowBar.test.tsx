import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import LeftToolWindowBar from '../LeftToolWindowBar'
import { useLayoutStore } from '../../../stores/layout-store'

function countActiveRailButtons(html: string) {
  return (html.match(/linear-gradient\(180deg/g) ?? []).length
}

describe('LeftToolWindowBar', () => {
  it('renders visible Chinese labels for every left navigation item', () => {
    const html = renderToString(<LeftToolWindowBar />)

    for (const label of ['首页', '项目', '小说', '蓝图', '角色', '世界', 'AI', '任务', '设置']) {
      expect(html).toContain(label)
    }
  })

  it('does not render legacy sidebar labels as primary nav labels', () => {
    const html = renderToString(<LeftToolWindowBar />)

    expect(html).not.toContain('项目结构</span>')
    expect(html).not.toContain('知识库</span>')
    expect(html).not.toContain('角色管理</span>')
  })

  it('keeps exactly one primary rail item visually active', () => {
    useLayoutStore.setState({
      sidebarOpen: true,
      sidebarView: 'project',
      aiPanelOpen: true,
      rightView: 'agent',
      bottomPanelOpen: true,
      bottomTab: 'models',
    })

    const html = renderToString(<LeftToolWindowBar />)

    expect(countActiveRailButtons(html)).toBe(1)
  })

  it('uses the AI rail entry to open model API configuration', () => {
    const source = renderToString(<LeftToolWindowBar />)

    expect(source).toContain('配置模型 API')
  })
})
