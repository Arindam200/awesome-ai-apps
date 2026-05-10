import React, { useState } from 'react'
import { BaseNode, NoopNodeProps } from 'motia/workbench'
import { Button, Input } from '@motiadev/ui'


export const Node: React.FC<NoopNodeProps> = (data) => {
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setIsLoading(true)
    try {
      const response = await fetch('/finance-query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: query.trim() }),
      })

      if (response.ok) {
        const result = await response.json()
        console.log('Analysis started:', result)
        setQuery('')
      } else {
        console.error('Failed to start analysis')
      }
    } catch (error) {
      console.error('Error starting analysis:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <BaseNode title="Finance Query Starter" variant="noop" {...data} disableTargetHandle>
      <div className="space-y-4">
        <div className="text-sm text-gray-400">
          Enter a stock symbol or company name to analyze
        </div>
        
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            type="text"
            placeholder="e.g., AAPL, Tesla, Microsoft"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading}
            className="w-full"
            data-testid="finance-query-input"
          />
          
          <Button 
            type="submit"
            variant="accent" 
            disabled={!query.trim() || isLoading}
            data-testid="start-analysis-button"
            className="w-full"
          >
            {isLoading ? 'Starting Analysis...' : 'Start Analysis'}
          </Button>
        </form>
        
        <div className="text-xs text-gray-500">
          Examples: AAPL, TSLA, MSFT, or "Apple stock analysis"
        </div>
      </div>
    </BaseNode>
  )
}
