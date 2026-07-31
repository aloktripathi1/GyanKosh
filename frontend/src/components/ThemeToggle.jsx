import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

function getInitialTheme() {
  const stored = localStorage.getItem("gyankosh-theme");
  if (stored) return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("gyankosh-theme", theme);
  }, [theme]);

  return (
    <button
      className="btn btn-secondary"
      style={{ padding: "var(--space-2)" }}
      onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
      aria-label="Toggle theme"
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
