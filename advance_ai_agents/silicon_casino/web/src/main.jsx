import React from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { queryClient } from './lib/queryClient.js'
import { SpectatorProvider } from './state/useSpectatorStore.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <SpectatorProvider>
        <App />
      </SpectatorProvider>
    </BrowserRouter>
  </QueryClientProvider>
)
