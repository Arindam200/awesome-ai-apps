import type { Meta, StoryObj } from '@storybook/react' // eslint-disable-line storybook/no-renderer-packages
import { Switch } from '../components/ui/Switch'
import { useState } from 'react'

const meta = {
  title: 'AI Novel Writer UI/Switch',
  component: Switch,
  tags: ['autodocs'],
  argTypes: {
    disabled: {
      control: 'boolean',
    },
  },
  parameters: {
    docs: {
      description: {
        component: 'Toggle switch component for boolean settings.',
      },
    },
  },
} satisfies Meta<typeof Switch>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => {
    const [checked, setChecked] = useState(false)
    return <Switch checked={checked} onCheckedChange={setChecked} {...args} />
  },
}

export const Controlled: Story = {
  render: () => {
    const [enabled, setEnabled] = useState(true)
    return (
      <div className="flex items-center gap-3">
        <Switch checked={enabled} onCheckedChange={setEnabled} />
        <span className="text-sm text-[var(--color-text)]">
          {enabled ? 'Enabled' : 'Disabled'}
        </span>
      </div>
    )
  },
}

export const Disabled: Story = {
  render: () => (
    <div className="flex gap-4">
      <Switch disabled defaultChecked />
      <Switch disabled />
    </div>
  ),
}
