import { Link, Outlet } from "react-router-dom";
import { BookOpen } from "lucide-react";
import ThemeToggle from "./ThemeToggle.jsx";

export default function Layout() {
  return (
    <>
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "var(--space-5) var(--space-5) 0" }}>
        <div className="row-between">
          <Link to="/" style={{ textDecoration: "none", color: "inherit" }}>
            <span className="brand-mark">
              <span className="logo-glyph">
                <BookOpen size={16} strokeWidth={2.5} />
              </span>
              GyanKosh
            </span>
          </Link>
          <ThemeToggle />
        </div>
      </div>
      <Outlet />
    </>
  );
}
