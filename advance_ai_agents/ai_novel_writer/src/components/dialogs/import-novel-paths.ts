export function inferImportedNovelProjectName(filePath: string): string {
  const fileName = filePath.split(/[\\/]/).pop() || ''
  return fileName.replace(/\.(txt|md|text)$/i, '') || '导入小说'
}
