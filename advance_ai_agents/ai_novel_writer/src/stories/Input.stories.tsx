import type { Meta, StoryObj } from '@storybook/react' // eslint-disable-line storybook/no-renderer-packages
import { Input } from '../components/ui/Input'

const meta = {
  title: 'AI Novel Writer UI/Input',
  component: Input,
  tags: ['autodocs'],
  argTypes: {
    type: {
      control: 'select',
      options: ['text', 'number', 'password', 'email'],
      description: 'Input type',
    },
    disabled: {
      control: 'boolean',
    },
    placeholder: {
      control: 'text',
    },
  },
  parameters: {
    docs: {
      description: {
        component: 'Vela input component. Number type has enhanced blur fallback behavior.',
      },
    },
  },
} satisfies Meta<typeof Input>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    placeholder: 'Enter text...',
    type: 'text',
  },
}

export const NumberInput: Story = {
  args: {
    type: 'number',
    min: 0,
    max: 100,
    defaultValue: 50,
    placeholder: '0-100',
  },
}

export const Disabled: Story = {
  args: {
    placeholder: 'Disabled input',
    disabled: true,
    value: 'Cannot edit',
  },
}

export const WithLabel: Story = {
  render: () => (
    <div className="flex flex-col gap-1.5 w-64">
      <label className="text-xs text-[var(--color-text-secondary)]">Username</label>
      <Input placeholder="Enter username..." />
    </div>
  ),
}
