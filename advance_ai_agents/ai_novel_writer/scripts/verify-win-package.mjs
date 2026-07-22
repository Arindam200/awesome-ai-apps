import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const scriptPath = fileURLToPath(import.meta.url)
const repositoryRoot = path.resolve(path.dirname(scriptPath), '..')

export function findLanceBinding(unpackedDir) {
  const packageDir = path.join(
    unpackedDir,
    'resources',
    'app.asar.unpacked',
    'node_modules',
    '@lancedb',
    'lancedb-win32-x64-msvc',
  )
  if (!existsSync(packageDir)) return null

  const pending = [packageDir]
  while (pending.length > 0) {
    const current = pending.pop()
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const fullPath = path.join(current, entry.name)
      if (entry.isDirectory()) pending.push(fullPath)
      if (entry.isFile() && entry.name.endsWith('.node')) return fullPath
    }
  }
  return null
}

export function verifyWindowsPackage(unpackedDir) {
  const asar = path.join(unpackedDir, 'resources', 'app.asar')
  const executable = path.join(unpackedDir, 'AI小说作家.exe')
  for (const required of [asar, executable]) {
    if (!existsSync(required)) throw new Error(`Missing required package file: ${required}`)
  }

  const nativeBinding = findLanceBinding(unpackedDir)
  if (!nativeBinding) throw new Error('Missing LanceDB Windows native binding')

  return { asar, executable, nativeBinding }
}

export function verifyPackagedLanceLoad(unpackedDir, runner = spawnSync) {
  const executable = path.join(unpackedDir, 'AI小说作家.exe')
  const marker = 'PACKAGED_LANCEDB_LOAD_OK'
  const result = runner(
    executable,
    [
      '-e',
      `require('./resources/app.asar/node_modules/@lancedb/lancedb'); process.stdout.write('${marker}')`,
    ],
    {
      cwd: unpackedDir,
      env: { ...process.env, ELECTRON_RUN_AS_NODE: '1' },
      encoding: 'utf8',
      windowsHide: true,
    },
  )

  if (result.status !== 0) {
    throw new Error(`Packaged LanceDB load failed: ${String(result.stderr ?? '').trim()}`)
  }
  if (!String(result.stdout ?? '').includes(marker)) {
    throw new Error('Packaged LanceDB load did not return its success marker')
  }
  return marker
}

if (process.argv[1] && path.resolve(process.argv[1]) === scriptPath) {
  const packageJson = JSON.parse(readFileSync(path.join(repositoryRoot, 'package.json'), 'utf8'))
  const unpackedDir = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.join(repositoryRoot, 'release', packageJson.version, 'win-unpacked')
  const result = verifyWindowsPackage(unpackedDir)
  const loadMarker = verifyPackagedLanceLoad(unpackedDir)
  console.log(`Verified Windows package: ${result.executable}`)
  console.log(`Verified LanceDB native binding: ${result.nativeBinding}`)
  console.log(`Verified packaged LanceDB load: ${loadMarker}`)
}
