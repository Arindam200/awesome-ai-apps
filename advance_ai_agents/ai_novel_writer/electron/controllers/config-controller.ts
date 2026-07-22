import { ipcMain } from 'electron'
import { readJsonFile, writeJsonFile, GLOBAL_CONFIG_PATH, DEFAULT_GLOBAL_CONFIG, VELA_HOME } from '../utils/config-utils'
import { GlobalConfig } from '../../src/shared/ipc-channels'

export function registerConfigController() {
  /** 读取全局配置 */
  ipcMain.handle('config:get', async () => {
    return readJsonFile<GlobalConfig>(GLOBAL_CONFIG_PATH, DEFAULT_GLOBAL_CONFIG)
  })

  /** 保存全局配置 */
  ipcMain.handle('config:set', async (_event, config: Partial<GlobalConfig>) => {
    try {
      const existing = readJsonFile<GlobalConfig>(GLOBAL_CONFIG_PATH, DEFAULT_GLOBAL_CONFIG)
      const updated = { ...existing, ...config }
      writeJsonFile(GLOBAL_CONFIG_PATH, updated)
      return { success: true }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })

  /** 获取 ~/.vela 路径 */
  ipcMain.handle('config:get-vela-home', async () => {
    return VELA_HOME
  })
}
