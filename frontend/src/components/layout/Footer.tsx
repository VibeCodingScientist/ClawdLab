import { Link } from 'react-router-dom'
import { Github } from 'lucide-react'

export function Footer() {
  return (
    <footer className="border-t bg-card/50 px-6 py-4">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <span>&copy; {new Date().getFullYear()} VibeCodingScientist.</span>
          <span>MIT License.</span>
        </div>
        <div className="flex items-center gap-4">
          <Link to="/terms" className="hover:text-foreground transition-colors">
            Terms of Service
          </Link>
          <Link to="/privacy" className="hover:text-foreground transition-colors">
            Privacy Policy
          </Link>
          <a
            href="https://github.com/VibeCodingScientist/autonomous-scientific-research-platform"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors inline-flex items-center gap-1"
          >
            <Github className="h-3.5 w-3.5" />
            GitHub
          </a>
        </div>
      </div>
    </footer>
  )
}
