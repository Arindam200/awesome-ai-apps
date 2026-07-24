import { describe, expect, it } from 'vitest'

import { inferImportedNovelProjectName } from '../import-novel-paths'

describe('inferImportedNovelProjectName', () => {
  it('extracts the file stem from a Windows absolute path', () => {
    expect(inferImportedNovelProjectName('C:\\Users\\EthanQ\\OneDrive\\Desktop\\蓝天航空公司的空姐.txt')).toBe('蓝天航空公司的空姐')
  })

  it('extracts the file stem from a POSIX path', () => {
    expect(inferImportedNovelProjectName('/Users/ethan/books/Novel.md')).toBe('Novel')
  })
})
