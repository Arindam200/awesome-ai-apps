import { ipcMain } from 'electron'
import fs from 'node:fs'
import fsPromises from 'node:fs/promises'
import path from 'node:path'
import { FileNode } from '../../src/shared/ipc-channels'

// 全局文件操作锁（按文件绝对路径分配 Mutex 队列）
const fileMutexMap = new Map<string, Promise<void>>()

/** 互斥锁执行器：确保同一文件的读写完全串行排队 */
async function withFileMutex<T>(filePath: string, task: () => Promise<T>): Promise<T> {
  // Normalize path across OS
  const normalPath = path.resolve(filePath)
  const previousTask = fileMutexMap.get(normalPath) || Promise.resolve()

  const currentTask = (async () => {
    try {
      await previousTask
    } catch { /* 前置任务错误不影响后续任务启动 */ }
    return task()
  })()

  // 缓存 stored promise 引用，供 finally 比较用
  const stored = currentTask.then(() => {}).catch(() => {})
  fileMutexMap.set(normalPath, stored)

  try {
    return await currentTask
  } finally {
    // 垃圾回收防御：如果当前任务是最后在等待的，则移除记录
    if (fileMutexMap.get(normalPath) === stored) {
      fileMutexMap.delete(normalPath)
    }
  }
}

export function registerFSController() {
  // 安全的异步读取
  ipcMain.handle('fs:read-file', async (_event, filePath: string) => {
    try {
      return await withFileMutex(filePath, async () => {
        const content = await fsPromises.readFile(filePath, 'utf-8')
        return { success: true, content }
      })
    } catch (error) {
      return { success: false, content: '', error: String(error) }
    }
  })

  // 跨平台绝对安全异步写入（防踩空）
  ipcMain.handle('fs:write-file', async (_event, filePath: string, content: string) => {
    try {
      return await withFileMutex(filePath, async () => {
        await fsPromises.mkdir(path.dirname(filePath), { recursive: true })
        // 先写到临时文件再原位替换，绝对防止 0KB 碎屑踩空现象
        const tempPath = `${filePath}.${Date.now()}.tmp`
        await fsPromises.writeFile(tempPath, content, 'utf-8')
        await fsPromises.rename(tempPath, filePath)
        return { success: true }
      })
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })

  ipcMain.handle('fs:list-dir', async (_event, dirPath: string): Promise<FileNode[]> => {
    try {
      return readDirRecursive(dirPath)
    } catch {
      return []
    }
  })

  ipcMain.handle('fs:mkdir', async (_event, dirPath: string) => {
    try {
      fs.mkdirSync(dirPath, { recursive: true })
      return { success: true }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })

  ipcMain.handle('fs:check-exists', async (_event, filePath: string) => {
    return fs.existsSync(filePath)
  })

  ipcMain.handle('fs:read-json', async (_event, filePath: string) => {
    try {
      return await withFileMutex(filePath, async () => {
        const content = await fsPromises.readFile(filePath, 'utf-8')
        return { success: true, data: JSON.parse(content) }
      })
    } catch (error) {
      return { success: false, data: null, error: String(error) }
    }
  })

  ipcMain.handle('fs:write-json', async (_event, filePath: string, data: unknown) => {
    try {
      return await withFileMutex(filePath, async () => {
        await fsPromises.mkdir(path.dirname(filePath), { recursive: true })
        const tempPath = `${filePath}.${Date.now()}.tmp`
        await fsPromises.writeFile(tempPath, JSON.stringify(data, null, 2), 'utf-8')
        await fsPromises.rename(tempPath, filePath)
        return { success: true }
      })
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })
}

function readDirRecursive(dirPath: string): FileNode[] {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true })
  return entries
    .filter((e) => !e.name.startsWith('.'))
    .sort((a, b) => {
      if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1
      return a.name.localeCompare(b.name, 'zh-CN')
    })
    .map((entry) => {
      const fullPath = path.join(dirPath, entry.name)
      if (entry.isDirectory()) {
        return { name: entry.name, path: fullPath, isDir: true, children: readDirRecursive(fullPath) }
      }
      return { name: entry.name, path: fullPath, isDir: false }
    })
}
