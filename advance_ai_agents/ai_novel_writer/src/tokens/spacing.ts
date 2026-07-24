/**
 * Vela Spacing Scale
 *
 * Usage:
 *   import { spacing } from '@/tokens/spacing'
 *   <div className={spacing[4]}>  // 16px
 */

export const spacing = {
  '0': '0',
  '1': '4px', // 0.25rem — tight grouping within component
  '2': '8px', // 0.5rem — default internal component spacing
  '3': '12px', // 0.75rem — component-to-component padding
  '4': '16px', // 1rem — section padding
  '5': '20px', // 1.25rem — large gaps
  '6': '24px', // 1.5rem — panel padding
  '8': '32px', // 2rem — major section separation
  '10': '40px', // 2.5rem — layout-level spacing
  '12': '48px', // 3rem — maximum spacing
  '16': '64px', // 4rem — page-level spacing
} as const

export type SpacingKey = keyof typeof spacing

// Tailwind equivalent mapping for direct usage in classes
export const tailwindSpacing: Record<SpacingKey, string> = {
  '0': '0',
  '1': '1',
  '2': '2',
  '3': '3',
  '4': '4',
  '5': '5',
  '6': '6',
  '8': '8',
  '10': '10',
  '12': '12',
  '16': '16',
}
