import { Link, Outlet } from "react-router-dom";
import ThemeToggle from "./ThemeToggle.jsx";

export default function Layout() {
  return (
    <>
      <header className="masthead">
        <div className="masthead-inner">
          <Link to="/" style={{ textDecoration: "none" }}>
            <span className="brand-mark">
              <span className="brand-glyph">Gyan</span>Kosh
            </span>
          </Link>
          <div className="row" style={{ gap: "var(--space-4)" }}>
            <Link to="/library" className="nav-link">
              Library
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <Outlet />
    </>
  );
}
