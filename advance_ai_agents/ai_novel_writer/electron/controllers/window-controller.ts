import { BrowserWindow, ipcMain, type IpcMainInvokeEvent } from 'electron'

function getSenderWindow(event: IpcMainInvokeEvent): BrowserWindow | null {
  return BrowserWindow.fromWebContents(event.sender)
}

export function registerWindowController() {
  ipcMain.handle('window:minimize', async (event) => {
    const win = getSenderWindow(event)
    win?.minimize()
    return { success: !!win }
  })

  ipcMain.handle('window:toggle-maximize', async (event) => {
    const win = getSenderWindow(event)
    if (!win) return { success: false }

    if (win.isMaximized()) {
      win.unmaximize()
    } else {
      win.maximize()
    }

    return { success: true, maximized: win.isMaximized() }
  })

  ipcMain.handle('window:close', async (event) => {
    const win = getSenderWindow(event)
    win?.close()
    return { success: !!win }
  })
}
