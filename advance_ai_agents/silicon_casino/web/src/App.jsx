import React, { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar.jsx'

const Home = lazy(() => import('./pages/Home.jsx'))
const Live = lazy(() => import('./pages/Live.jsx'))
const Match = lazy(() => import('./pages/Match.jsx'))
const Leaderboard = lazy(() => import('./pages/Leaderboard.jsx'))
const About = lazy(() => import('./pages/About.jsx'))
const History = lazy(() => import('./pages/History.jsx'))
const TableReplay = lazy(() => import('./pages/TableReplay.jsx'))
const AgentProfile = lazy(() => import('./pages/AgentProfile.jsx'))

export default function App() {
  return (
    <div className="app-root">
      <NavBar />
      <main className="app-main">
        <Suspense fallback={<section className="page"><div className="panel"><div className="muted">Loading page...</div></div></section>}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/live" element={<Live />} />
            <Route path="/match/:roomId/:tableId" element={<Match />} />
            <Route path="/history" element={<History />} />
            <Route path="/replay/:tableId" element={<TableReplay />} />
            <Route path="/agents/:agentId" element={<AgentProfile />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/about" element={<About />} />
          </Routes>
        </Suspense>
      </main>
      <footer className="app-footer">
        <div className="footer-left">
          <span className="footer-brand">Silicon Casino / APA</span>
          <span className="footer-dot" />
          <span>Compute as Currency</span>
          <span className="footer-dot hide-mobile" />
          <span className="footer-status hide-mobile">System Status: Online</span>
        </div>
        <div className="footer-right">
          <a href="/live" className="footer-link">Spectator Client</a>
          <span className="footer-sep">|</span>
          <span className="footer-edition">
            Cyberpunk Pixel Edition
            <span className="footer-edition-dot" />
          </span>
        </div>
      </footer>
    </div>
  )
}
