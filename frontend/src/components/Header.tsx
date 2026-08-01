import { Link } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import {
  Menu,
  X,
  Sun,
  Moon,
  LogOut,
  User,
  Home,
  Box,
  Shirt,
  MessageSquare,
  LayoutGrid,
  Ruler,
  Palette,
  Users,
  History,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/useAuth";

// Core, daily-use features — always visible.
const PRIMARY = [
  { to: "/", label: "Home", icon: Home },
  { to: "/avatar", label: "Avatar", icon: Box },
  { to: "/try-on", label: "Try On", icon: Shirt },
  { to: "/stylist", label: "Chat", icon: MessageSquare },
] as const;

// Supporting tools — tucked into "Explore".
const MORE = [
  { to: "/wardrobe", label: "Wardrobe", icon: LayoutGrid, desc: "Your saved garments & outfits" },
  { to: "/size", label: "My Size", icon: Ruler, desc: "Size recommendations by brand" },
  { to: "/colors", label: "Colors", icon: Palette, desc: "Shades that suit you" },
  { to: "/feed", label: "Feed", icon: Users, desc: "Share fits, get votes" },
  { to: "/history", label: "History", icon: History, desc: "Your past try-ons" },
] as const;

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
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground">
            <span className="text-sm font-bold text-background">FC</span>
          </div>
          <span className="font-heading text-lg font-semibold tracking-tight text-foreground">
            FitCheck AI
          </span>
        </Link>

        {/* Desktop */}
        <nav className="hidden items-center gap-1 lg:flex">
          {user && (
            <>
              {PRIMARY.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  activeOptions={{ exact: link.to === "/" }}
                  activeProps={{ className: "text-foreground font-medium" }}
                  inactiveProps={{ className: "text-muted-foreground hover:text-foreground" }}
                  className="rounded-md px-3 py-2 text-sm transition-colors"
                >
                  {link.label}
                </Link>
              ))}

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-1 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground focus:outline-none">
                    Explore
                    <ChevronDown className="h-3.5 w-3.5" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64">
                  <DropdownMenuLabel className="text-xs uppercase tracking-wider text-muted-foreground">
                    More tools
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {MORE.map((item) => (
                    <DropdownMenuItem key={item.to} asChild className="cursor-pointer">
                      <Link to={item.to} className="flex items-start gap-3 py-2">
                        <item.icon className="mt-0.5 h-4 w-4 text-muted-foreground" />
                        <span className="flex flex-col">
                          <span className="text-sm font-medium text-foreground">{item.label}</span>
                          <span className="text-xs text-muted-foreground">{item.desc}</span>
                        </span>
                      </Link>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}

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
          {user ? (
            <nav className="flex flex-col gap-1">
              {PRIMARY.map((link) => (
                <MobileLink key={link.to} {...link} onClick={() => setMobileOpen(false)} />
              ))}
              <p className="mt-3 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Explore
              </p>
              {MORE.map((item) => (
                <MobileLink key={item.to} {...item} onClick={() => setMobileOpen(false)} />
              ))}
              <button
                type="button"
                onClick={() => {
                  logout();
                  setMobileOpen(false);
                }}
                className="mt-3 flex items-center gap-2 rounded-md border-t border-border px-3 pt-3 text-left text-sm text-muted-foreground hover:text-foreground"
              >
                <LogOut className="h-4 w-4" />
                Log out ({user.display_name || user.email.split("@")[0]})
              </button>
            </nav>
          ) : (
            <div className="flex flex-col gap-2">
              <Link to="/login" search={{ redirect: "" }} onClick={() => setMobileOpen(false)}>
                <Button variant="outline" className="w-full">Log in</Button>
              </Link>
              <Link to="/login" search={{ redirect: "" }} onClick={() => setMobileOpen(false)}>
                <Button className="w-full bg-foreground text-background hover:bg-foreground/90">
                  Get started
                </Button>
              </Link>
            </div>
          )}
        </div>
      )}
    </header>
  );
}

function MobileLink({
  to,
  label,
  icon: Icon,
  onClick,
}: {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      activeOptions={{ exact: to === "/" }}
      activeProps={{ className: "bg-accent text-foreground font-medium" }}
      className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}
