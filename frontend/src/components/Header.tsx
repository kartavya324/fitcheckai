import { Link } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { Menu, X, Sun, Moon, LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/useAuth";

const NAV_LINKS = [
  { to: "/avatar", label: "Avatar" },
  { to: "/try-on", label: "Try On" },
  { to: "/wardrobe", label: "Wardrobe" },
  { to: "/stylist", label: "Stylist" },
  { to: "/size", label: "My Size" },
  { to: "/colors", label: "Colors" },
  { to: "/feed", label: "Feed" },
  { to: "/history", label: "History" },
];

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const { user, logout } = useAuth();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  const DarkToggle = (
    <Button variant="ghost" size="icon" onClick={() => setDark(!dark)} title="Toggle theme">
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to={user ? "/avatar" : "/"} className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground">
            <span className="text-sm font-bold text-background">FC</span>
          </div>
          <span className="font-heading text-lg font-semibold tracking-tight text-foreground">
            FitCheck AI
          </span>
        </Link>

        {/* Desktop */}
        <nav className="hidden items-center gap-1 lg:flex">
          {/* App nav — only when signed in (nothing to wander into logged out) */}
          {user &&
            NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                activeProps={{ className: "text-foreground font-medium" }}
                inactiveProps={{ className: "text-muted-foreground hover:text-foreground" }}
                className="rounded-md px-3 py-2 text-sm transition-colors"
              >
                {link.label}
              </Link>
            ))}
          {DarkToggle}
          {user ? (
            <div className="ml-2 flex items-center gap-2 border-l border-border pl-3">
              <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <User className="h-4 w-4" />
                {user.display_name || user.email.split("@")[0]}
              </span>
              <Button variant="ghost" size="icon" onClick={logout} title="Log out">
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="ml-2 flex items-center gap-2">
              <Link to="/login" search={{ redirect: "" }}>
                <Button variant="ghost">Log in</Button>
              </Link>
              <Link to="/login" search={{ redirect: "" }}>
                <Button className="bg-foreground text-background hover:bg-foreground/90">
                  Get started
                </Button>
              </Link>
            </div>
          )}
        </nav>

        {/* Mobile trigger */}
        <div className="flex items-center gap-2 lg:hidden">
          {DarkToggle}
          <Button variant="ghost" size="icon" onClick={() => setMobileOpen(!mobileOpen)}>
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="border-t border-border bg-background px-4 py-4 lg:hidden">
          <nav className="flex flex-col gap-1">
            {user ? (
              <>
                {NAV_LINKS.map((link) => (
                  <Link
                    key={link.to}
                    to={link.to}
                    onClick={() => setMobileOpen(false)}
                    activeProps={{ className: "bg-accent text-foreground font-medium" }}
                    className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    setMobileOpen(false);
                  }}
                  className="mt-1 flex items-center gap-2 rounded-md border-t border-border px-3 pt-3 text-left text-sm text-muted-foreground hover:text-foreground"
                >
                  <LogOut className="h-4 w-4" />
                  Log out ({user.display_name || user.email.split("@")[0]})
                </button>
              </>
            ) : (
              <>
                <Link to="/login" search={{ redirect: "" }} onClick={() => setMobileOpen(false)}>
                  <Button variant="outline" className="w-full">Log in</Button>
                </Link>
                <Link to="/login" search={{ redirect: "" }} onClick={() => setMobileOpen(false)}>
                  <Button className="mt-2 w-full bg-foreground text-background hover:bg-foreground/90">
                    Get started
                  </Button>
                </Link>
              </>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
