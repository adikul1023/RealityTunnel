"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, X } from "lucide-react";
import { OLDoc, getCoverUrl, searchBooks } from "@/app/lib/openlibrary";

export default function Hero() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<OLDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (query.length < 2) { setResults([]); setOpen(false); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      const docs = await searchBooks(query, 6);
      setResults(docs);
      setOpen(true);
      setLoading(false);
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query]);

  return (
    <section className="relative min-h-[92vh] flex flex-col items-center justify-center overflow-hidden">
      {/* Background layers */}
      <div className="absolute inset-0 bg-gradient-to-br from-[var(--bg)] via-[#2C2723] to-[var(--card)]" />
      <div className="paper-texture absolute inset-0 opacity-40" />
      {/* Decorative blurred circles */}
      <div className="absolute top-20 right-20 w-80 h-80 rounded-full bg-[var(--primary)]/10 blur-3xl" />
      <div className="absolute bottom-20 left-10 w-96 h-96 rounded-full bg-[var(--primary-dark)]/10 blur-3xl" />
      {/* Vignette */}
      <div className="absolute inset-0 bg-radial-[ellipse_at_center] from-transparent via-transparent to-black/10 pointer-events-none" />

      <div className="relative z-10 flex flex-col items-center text-center px-6 max-w-3xl w-full">
        {/* Wordmark */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="flex items-center gap-3 mb-8"
        >
          <span className="text-4xl">📚</span>
          <span
            style={{ fontFamily: "'Merriweather', serif", color: "var(--primary)" }}
            className="text-2xl font-bold tracking-tight"
          >
            ReviewBook
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          style={{ fontFamily: "'Merriweather', serif", color: "var(--text)" }}
          className="text-5xl md:text-6xl font-black leading-tight mb-4"
        >
          Discover your next
          <br />
          <span style={{ color: "var(--primary)" }}>favorite book.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-lg text-[var(--secondary)] mb-10"
        >
          Millions of books from every genre, all in one place.
        </motion.p>

        {/* Search bar */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="relative w-full max-w-2xl"
        >
          <div className="relative flex items-center bg-[var(--card)] rounded-2xl shadow-[0_8px_40px_rgba(0,0,0,0.4)] border border-[var(--border)]">
            <Search className="absolute left-5 text-[var(--secondary)]" size={20} />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => results.length > 0 && setOpen(true)}
              placeholder="Search books, authors, ISBN..."
              className="w-full py-5 pl-14 pr-14 text-lg bg-transparent outline-none text-[var(--text)] placeholder:text-[#6b6156]"
              style={{ fontFamily: "'Inter', sans-serif" }}
            />
            {query && (
              <button
                onClick={() => { setQuery(""); setResults([]); setOpen(false); inputRef.current?.focus(); }}
                className="absolute right-5 text-[#6b6156] hover:text-[var(--primary)] transition-colors"
              >
                <X size={20} />
              </button>
            )}
          </div>

          {/* Autocomplete dropdown */}
          <AnimatePresence>
            {open && (results.length > 0 || loading) && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.18 }}
                className="absolute top-full mt-2 w-full bg-[var(--card)] rounded-2xl shadow-[0_16px_60px_rgba(0,0,0,0.5)] border border-[var(--border)] z-50 overflow-hidden"
              >
                {loading && (
                  <div className="px-6 py-4 text-[var(--secondary)] text-sm">Searching…</div>
                )}
                {!loading && results.map((book, i) => (
                  <a
                    key={book.key}
                    href={`https://openlibrary.org${book.key}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-4 px-6 py-3 hover:bg-[var(--bg)] transition-colors cursor-pointer border-b border-[var(--border)] last:border-0"
                  >
                    {/* Mini cover */}
                    <div className="w-9 h-12 flex-shrink-0 rounded overflow-hidden bg-[var(--bg)]">
                      {book.cover_i ? (
                        <img
                          src={getCoverUrl(book.cover_i, "S")}
                          alt={book.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[var(--secondary)] text-xs">📖</div>
                      )}
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-[var(--text)] text-sm leading-tight">{book.title}</p>
                      <p className="text-[var(--secondary)] text-xs">{book.author_name?.[0] ?? "Unknown Author"}</p>
                    </div>
                  </a>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Quick genre tags */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="flex flex-wrap justify-center gap-2 mt-6"
        >
          {["Fantasy", "Sci-Fi", "Mystery", "Biography", "Programming"].map((g) => (
            <button
              key={g}
              onClick={() => { setQuery(g); inputRef.current?.focus(); }}
              className="px-4 py-1.5 rounded-full text-sm font-medium border border-[var(--primary)] text-[var(--primary)] bg-[var(--primary)]/10 hover:bg-[var(--primary)]/25 transition-colors"
            >
              {g}
            </button>
          ))}
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2 }}
        className="absolute bottom-10 flex flex-col items-center gap-1 text-[var(--secondary)]"
      >
        <span className="text-xs tracking-widest uppercase">Scroll</span>
        <motion.div
          animate={{ y: [0, 6, 0] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
          className="w-0.5 h-6 bg-[var(--primary)] rounded-full"
        />
      </motion.div>
    </section>
  );
}
