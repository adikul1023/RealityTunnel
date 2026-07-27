import Link from "next/link";

const LINKS = [
  { label: "About", href: "#" },
  { label: "Privacy", href: "#" },
  { label: "Terms", href: "#" },
  { label: "Contact", href: "#" },
  { label: "Open Library", href: "https://openlibrary.org", external: true },
];

export default function Footer() {
  return (
    <footer className="bg-[var(--card)] border-t border-[var(--border)] py-12 mt-auto">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
          {/* Brand */}
          <div className="md:col-span-1 flex flex-col items-start">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-3xl">📚</span>
              <span
                style={{ fontFamily: "'Merriweather', serif" }}
                className="text-xl font-bold text-[var(--primary)] tracking-tight"
              >
                ReviewBook
              </span>
            </div>
            <p className="text-[var(--secondary)] text-sm mb-4">
              Your gateway to millions of books. Powered by the free and open Open Library API.
            </p>
          </div>

          <div>
            <h4 className="font-bold text-[var(--text)] mb-4">Explore</h4>
            <ul className="space-y-2 text-sm text-[var(--secondary)]">
              <li><a href="#" className="hover:text-[var(--primary)] transition-colors">Trending</a></li>
              <li><a href="#" className="hover:text-[var(--primary)] transition-colors">New Releases</a></li>
              <li><a href="#" className="hover:text-[var(--primary)] transition-colors">Staff Picks</a></li>
              <li><a href="#" className="hover:text-[var(--primary)] transition-colors">Top Authors</a></li>
            </ul>
          </div>

          {/* Links */}
          <nav className="flex flex-col gap-2">
            <h4 className="font-bold text-[var(--text)] mb-2">Company</h4>
            {LINKS.map((link) =>
              link.external ? (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-[var(--secondary)] hover:text-[var(--primary)] transition-colors"
                >
                  {link.label}
                </a>
              ) : (
                <a
                  key={link.label}
                  href={link.href}
                  className="text-sm text-[var(--secondary)] hover:text-[var(--primary)] transition-colors"
                >
                  {link.label}
                </a>
              )
            )}
          </nav>
        </div>

        {/* Credit */}
        <div className="pt-8 border-t border-[var(--border)] text-center text-sm text-[var(--secondary)] flex flex-col md:flex-row items-center justify-between">
          <p>© {new Date().getFullYear()} ReviewBook. All rights reserved.</p>
          <p className="mt-2 md:mt-0">
            Book data provided by{" "}
            <a
              href="https://openlibrary.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--primary)] hover:underline"
            >
              Open Library
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
