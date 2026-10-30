import { Link } from 'react-router-dom'
import Logo from './Logo'

export default function TopBar() {
  return (
    <header className="relative z-20 mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
      <Link to="/" aria-label="Ghost Profile Generator home" className="rounded-2xl transition-opacity hover:opacity-90">
        <Logo />
      </Link>
      <nav aria-label="Primary navigation">
        <Link to="/history" className="topbar-nav-link"><span className="topbar-nav-dot" /> scan history <span>↗</span></Link>
      </nav>
    </header>
  )
}
