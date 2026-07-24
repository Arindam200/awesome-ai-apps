import { existsSync, readFileSync, realpathSync, rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptPath = fileURLToPath(import.meta.url)
const repositoryRoot = path.resolve(path.dirname(scriptPath), '..')

export function resolveBuildTargets(root, version) {
  if (!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(version)) {
    throw new Error(`Unsafe package version: ${JSON.stringify(version)}`)
  }

  const resolvedRoot = path.resolve(root)
  const targets = [
    path.join(resolvedRoot, 'dist'),
    path.join(resolvedRoot, 'dist-electron'),
    path.join(resolvedRoot, 'release', version),
  ]

  for (const target of targets) {
    if (!target.startsWith(`${resolvedRoot}${path.sep}`)) {
      throw new Error(`Refusing to clean path outside repository: ${target}`)
    }
  }

  return targets
}

export function cleanBuildOutput(root = repositoryRoot) {
  const resolvedRoot = realpathSync(root)
  const packageJson = JSON.parse(readFileSync(path.join(resolvedRoot, 'package.json'), 'utf8'))
  const targets = resolveBuildTargets(resolvedRoot, packageJson.version)

  for (const target of targets) {
    if (existsSync(target)) rmSync(target, { recursive: true, force: true })
  }
  return targets
}

if (process.argv[1] && path.resolve(process.argv[1]) === scriptPath) {
  const targets = cleanBuildOutput()
  console.log(`Cleaned build outputs for ${targets.length} verified paths.`)
}
