import React, { useState } from 'react'
import { BaseNode, NoopNodeProps } from 'motia/workbench'
import { Button } from '@motiadev/ui'

export const Node: React.FC<NoopNodeProps> = (data) => {
  const [traceId, setTraceId] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleViewResults = async () => {
    if (!traceId.trim()) return

    setIsLoading(true)
    setError('')
    try {
      const resultUrl = `/finance-result/${traceId.trim()}`
      window.open(resultUrl, '_blank')
    } catch (error) {
      console.error('Error opening results:', error)
      setError('Failed to open results')
    } finally {
      setIsLoading(false)
    }
  }

  const handleQuickTest = async () => {
    setIsLoading(true)
    setError('')
    try {
      const response = await fetch('/finance-query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: 'AAPL' }),
      })

      if (response.ok) {
        const result = await response.json()
        const RESULT_DELAY_MS = 30000; // 30 seconds to allow for processing  
        if (result.traceId) {  
          setTraceId(result.traceId)  
          setTimeout(() => {  
            window.open(`/finance-result/${result.traceId}`, '_blank')  
          }, RESULT_DELAY_MS)  
        } else {
          setError('No traceId received from query')
        }
      } else {
        const errorData = await response.json().catch(() => ({}))
        setError(`Query failed: ${errorData.error || response.statusText}`)
      }
    } catch (error) {
      console.error('Error in quick test:', error)
      setError('Failed to perform quick test')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <BaseNode title="Result Viewer" variant="noop" {...data} disableSourceHandle>
      <div className="space-y-4">
        <div className="text-sm text-gray-400">
          View comprehensive analysis results
        </div>
        
        <div className="space-y-3">
          <div className="flex space-x-2">
            <input
              type="text"
              placeholder="Enter traceId (e.g., QGTFR-9217561)"
              value={traceId}
              onChange={(e) => setTraceId(e.target.value)}
              disabled={isLoading}
              className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm placeholder-gray-400"
              data-testid="trace-id-input"
            />
            
            <Button 
              onClick={handleViewResults}
              variant="accent" 
              disabled={!traceId.trim() || isLoading}
              data-testid="view-results-button"
              size="sm"
            >
              {isLoading ? 'Loading...' : 'View'}
            </Button>
          </div>
          
          {error && (
            <div className="text-red-400 text-xs">
              {error}
            </div>
          )}
          
          <div className="border-t border-gray-600 pt-3">
            <div className="text-xs text-gray-500 mb-2">
              Quick test with sample data:
            </div>
            <Button 
              onClick={handleQuickTest}
              variant="outline" 
              disabled={isLoading}
              data-testid="quick-test-button"
              size="sm"
              className="w-full"
            >
              {isLoading ? 'Testing...' : 'Quick Test (AAPL Analysis)'}
            </Button>
          </div>
        </div>
        
        <div className="text-xs text-gray-500">
          Results will open in a new tab showing comprehensive financial analysis.
        </div>
      </div>
    </BaseNode>
  )
}