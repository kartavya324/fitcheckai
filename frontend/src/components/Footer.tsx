import { Link } from "@tanstack/react-router";

export function Footer() {
  return (
    <footer className="border-t border-border bg-background">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground">
                <span className="text-sm font-bold text-background">FC</span>
              </div>
              <span className="font-heading text-lg font-semibold text-foreground">
                FitCheck AI
              </span>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              AI-powered virtual try-on. See how any outfit looks on you before buying.
            </p>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold text-foreground">Product</h4>
            <ul className="mt-3 space-y-2">
              <li><Link to="/" className="text-sm text-muted-foreground hover:text-foreground">Home</Link></li>
              <li><Link to="/try-on" className="text-sm text-muted-foreground hover:text-foreground">Try On</Link></li>
              <li><Link to="/history" className="text-sm text-muted-foreground hover:text-foreground">History</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold text-foreground">Company</h4>
            <ul className="mt-3 space-y-2">
              <li><span className="text-sm text-muted-foreground">About</span></li>
              <li><span className="text-sm text-muted-foreground">Blog</span></li>
              <li><span className="text-sm text-muted-foreground">Contact</span></li>
            </ul>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold text-foreground">Legal</h4>
            <ul className="mt-3 space-y-2">
              <li><span className="text-sm text-muted-foreground">Privacy</span></li>
              <li><span className="text-sm text-muted-foreground">Terms</span></li>
            </ul>
          </div>
        </div>
        <div className="mt-12 border-t border-border pt-8 text-center">
          <p className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} FitCheck AI. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
