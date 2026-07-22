import type { Meta, StoryObj } from '@storybook/react' // eslint-disable-line storybook/no-renderer-packages
import { useState } from 'react'
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/Dialog'
import { Button } from '../components/ui/Button'

const meta = {
  title: 'AI Novel Writer UI/Dialog',
  component: Dialog,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Modal dialog built on Radix UI primitives. Supports header, title, description, and footer sections.',
      },
    },
  },
} satisfies Meta

export default meta

export const Default: StoryObj = {
  render: () => {
    const [open, setOpen] = useState(false)
    return (
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button>Open Dialog</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>
              This is a description of the dialog content.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 text-sm text-[var(--color-text)]">
            Dialog content goes here. You can put any React content inside.
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={() => setOpen(false)}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )
  },
}

export const AlertDialog: StoryObj = {
  name: 'Alert Style',
  render: () => {
    const [open, setOpen] = useState(false)
    return (
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button variant="destructive">Delete Item</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Deletion</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this item? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={() => setOpen(false)}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )
  },
}
