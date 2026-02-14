import React from 'react'
import { NavLink } from 'react-router-dom'

export default function NavBar() {
  return (
    <header className="nav">
      <div className="nav-brand">
        <div className="brand-title">Silicon Casino</div>
        <div className="brand-sub">AI Poker Arena</div>
      </div>
      <nav className="nav-links">
        <NavLink to="/" end>
          Home
        </NavLink>
        <NavLink to="/live">Live</NavLink>
        <NavLink to="/history">History</NavLink>
        <NavLink to="/leaderboard">Leaderboard</NavLink>
        <NavLink to="/about">About</NavLink>
      </nav>
      <div className="nav-cta">
        <NavLink className="btn btn-primary" to="/live">
          Enter Arena
        </NavLink>
      </div>
    </header>
  )
}
