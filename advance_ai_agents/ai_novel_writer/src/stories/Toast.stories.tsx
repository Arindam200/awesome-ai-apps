import type { Meta, StoryObj } from '@storybook/react' // eslint-disable-line storybook/no-renderer-packages
import { toast } from '../components/ui/Toast'
import { Button } from '../components/ui/Button'

const meta = {
  title: 'AI Novel Writer UI/Toast',
  parameters: {
    docs: {
      description: {
        component: 'Global toast notification system. Use `toast.success()`, `toast.warning()`, `toast.info()` to show notifications.',
      },
    },
  },
} satisfies Meta

export default meta

export const Demo: StoryObj = {
  name: 'Toast Examples',
  render: () => (
    <div className="flex flex-wrap gap-3">
      <Button
        variant="default"
        onClick={() => toast.success('Document saved successfully')}
      >
        Success Toast
      </Button>
      <Button
        variant="warning"
        onClick={() => toast.warning('Word count exceeds limit')}
      >
        Warning Toast
      </Button>
      <Button
        variant="outline"
        onClick={() => toast.info('Tip: Use Ctrl+S to save')}
      >
        Info Toast
      </Button>
      <Button
        variant="destructive"
        onClick={() => toast.error('Failed to connect to server')}
      >
        Error Toast
      </Button>
    </div>
  ),
}
