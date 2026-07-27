"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Star } from "lucide-react";
import { OLDoc, getCoverUrl, getBooksBySubject, searchBooks } from "@/app/lib/openlibrary";

interface Props {
  genre: string | null;
}

function BookCard({ book, index }: { book: OLDoc; index: number }) {
  return (
    <motion.a
      href={`https://openlibrary.org${book.key}`}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ delay: index * 0.04, duration: 0.35 }}
      whileHover={{ y: -6, transition: { duration: 0.2 } }}
      className="group bg-[var(--card)] rounded-xl overflow-hidden border border-[var(--border)] shadow-sm hover:shadow-[0_12px_40px_rgba(0,0,0,0.4)] transition-shadow duration-300 flex flex-col"
    >
      {/* Cover */}
      <div className="relative aspect-[2/3] overflow-hidden bg-[var(--bg)]">
        {book.cover_i ? (
          <img
            src={getCoverUrl(book.cover_i, "M")}
            alt={book.title}
            className="w-full h-full object-cover transition-transform duration-400 group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center p-4 text-center">
            <span className="text-5xl mb-2 text-[var(--secondary)]">📖</span>
            <span className="text-[var(--primary)] text-xs font-medium leading-tight">{book.title}</span>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-4 flex flex-col flex-1">
        {book.ratings_average !== undefined && (
          <div className="flex items-center gap-0.5 mb-2">
            {[...Array(5)].map((_, i) => {
              const rounded = Math.round(book.ratings_average!);
              return (
                <Star
                  key={i}
                  size={12}
                  className={i < rounded ? "fill-[var(--primary)] text-[var(--primary)]" : "text-[var(--border)]"}
                />
              );
            })}
            <span className="text-xs text-[var(--secondary)] ml-1">{book.ratings_average.toFixed(1)}</span>
          </div>
        )}
        <h3 className="font-semibold text-[var(--text)] text-sm leading-snug line-clamp-2 mb-1 group-hover:text-[var(--primary)] transition-colors">
          {book.title}
        </h3>
        <p className="text-xs text-[var(--secondary)] line-clamp-1">{book.author_name?.[0] ?? "Unknown"}</p>

        <div className="mt-auto pt-3 flex flex-wrap gap-1">
          {book.subject?.slice(0, 2).map((s) => (
            <span key={s} className="px-2 py-0.5 rounded-full bg-[var(--bg-accent)] text-[var(--primary)] text-[10px] font-medium">
              {s.slice(0, 16)}
            </span>
          ))}
        </div>
      </div>
    </motion.a>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-[var(--card)] rounded-xl overflow-hidden border border-[var(--border)]">
      <div className="skeleton aspect-[2/3]" />
      <div className="p-4">
        <div className="skeleton h-3 w-12 mb-2" />
        <div className="skeleton h-4 w-full mb-1" />
        <div className="skeleton h-3 w-2/3" />
      </div>
    </div>
  );
}

export default function RecentlyAdded({ genre }: Props) {
  const [books, setBooks] = useState<OLDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const load = useCallback(async (g: string | null, reset: boolean, pageToLoad: number) => {
    setLoading(true);
    let docs: OLDoc[];
    const offset = (pageToLoad - 1) * 16;
    if (g) {
      docs = await getBooksBySubject(g, 16, offset);
    } else {
      docs = await searchBooks("fiction novel award", 16, offset);
    }
    setBooks(reset ? docs : (prev) => {
      // Filter out potential duplicates across pages
      const newDocs = docs.filter((d) => !prev.some((p) => p.key === d.key));
      return [...prev, ...newDocs];
    });
    setHasMore(docs.length >= 16);
    setLoading(false);
  }, []);

  useEffect(() => {
    setPage(1);
    load(genre, true, 1);
  }, [genre, load]);

  const onLoadMore = () => {
    const nextPage = page + 1;
    setPage(nextPage);
    load(genre, false, nextPage);
  };

  return (
    <section className="py-16 px-6 max-w-7xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="flex items-center justify-between mb-8"
      >
        <div>
          <h2 style={{ fontFamily: "'Merriweather', serif" }} className="text-3xl font-bold text-[var(--text)]">
            {genre ? `${genre} Books` : "Recently Added"}
          </h2>
          <p className="text-[var(--secondary)] mt-1 text-sm">Fresh arrivals in our catalog</p>
        </div>
      </motion.div>

      <AnimatePresence mode="wait">
        <motion.div
          key={genre ?? "all"}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-5"
        >
          {loading && books.length === 0
            ? Array.from({ length: 10 }).map((_, i) => <SkeletonCard key={i} />)
            : books.map((book, i) => <BookCard key={`${book.key}-${i}`} book={book} index={i} />)}
        </motion.div>
      </AnimatePresence>

      {hasMore && !loading && (
        <div className="mt-12 text-center">
          <button
            onClick={onLoadMore}
            className="px-8 py-3 rounded-full font-bold text-[var(--primary)] border-2 border-[var(--primary)] hover:bg-[var(--primary)] hover:text-[#111] transition-colors shadow-sm"
          >
            Load More Books
          </button>
        </div>
      )}

      {loading && books.length > 0 && (
        <div className="mt-12 text-center text-[var(--secondary)] animate-pulse font-medium">
          Loading...
        </div>
      )}
    </section>
  );
}
