const avatarModules = import.meta.glob('./avatars/avatar_*.png', { eager: true, import: 'default' })
const chipModules = import.meta.glob('./chips/chip_color_*_unit_*.png', { eager: true, import: 'default' })

export const CHIP_COLORS = ['red', 'blue', 'white', 'purple', 'green', 'pink', 'black', 'gold']
export const CHIP_UNITS = [1, 5, 25, 100]

const colorToId = Object.fromEntries(CHIP_COLORS.map((name, i) => [name, i + 1]))
const unitToId = Object.fromEntries(CHIP_UNITS.map((value, i) => [String(value), i + 1]))

const avatarList = Object.entries(avatarModules)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([, url]) => url)

const chipEntries = Object.entries(chipModules)
  .map(([path, url]) => {
    const m = path.match(/chip_color_(\d+)_unit_(\d+)\.png$/)
    if (!m) return null
    return { path, url, color: Number(m[1]), unit: Number(m[2]) }
  })
  .filter(Boolean)
  .sort((a, b) => (a.color - b.color) || (a.unit - b.unit))

const chipList = chipEntries.map((v) => v.url)
const chipColorCount = Math.max(1, ...chipEntries.map((v) => v.color), 1)
const chipUnitCount = Math.max(1, ...chipEntries.map((v) => v.unit), 1)
const chipMap = new Map(chipEntries.map((v) => [`${v.color}:${v.unit}`, v.url]))

export { avatarList, chipList }

export function avatarBySeat(seat = 0) {
  if (!avatarList.length) return ''
  const idx = Math.abs(Number(seat || 0)) % avatarList.length
  return avatarList[idx]
}

export function chipByIndex(index = 0) {
  if (!chipList.length) return ''
  const idx = Math.abs(Number(index || 0)) % chipList.length
  return chipList[idx]
}

export function chipBy(color = 1, unit = 1) {
  if (!chipList.length) return ''
  const c = ((Math.abs(Number(color || 1)) - 1) % chipColorCount) + 1
  const u = ((Math.abs(Number(unit || 1)) - 1) % chipUnitCount) + 1
  return chipMap.get(`${c}:${u}`) || chipList[0] || ''
}

export function chipByName(colorName = 'red', unitValue = 1) {
  const colorId = colorToId[String(colorName || '').toLowerCase()] || 1
  const unitId = unitToId[String(unitValue)] || 1
  return chipBy(colorId, unitId)
}
