import type { Meta, StoryObj } from '@storybook/react' // eslint-disable-line storybook/no-renderer-packages
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '../components/ui/Tooltip'
import { Button } from '../components/ui/Button'

const meta = {
  title: 'AI Novel Writer UI/Tooltip',
  component: Tooltip,
  parameters: {
    docs: {
      description: {
        component: 'Tooltip component based on Radix UI. Automatically adapts to light/dark themes.',
      },
    },
  },
} satisfies Meta

export default meta

export const Default: StoryObj = {
  render: () => (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="outline">Hover me</Button>
        </TooltipTrigger>
        <TooltipContent>Tooltip content</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  ),
}

export const AllPositions: StoryObj = {
  name: 'All Positions',
  render: () => (
    <TooltipProvider>
      <div className="flex gap-4 flex-wrap">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="sm">Top</Button>
          </TooltipTrigger>
          <TooltipContent side="top">Top tooltip</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="sm">Bottom</Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">Bottom tooltip</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="sm">Left</Button>
          </TooltipTrigger>
          <TooltipContent side="left">Left tooltip</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="sm">Right</Button>
          </TooltipTrigger>
          <TooltipContent side="right">Right tooltip</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  ),
}
