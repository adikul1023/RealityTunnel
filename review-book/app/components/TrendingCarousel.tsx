"use client";

import { useRef } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Star } from "lucide-react";
import { OLDoc, getCoverUrl, getGoodreadsSearchUrl } from "@/app/lib/openlibrary";

interface Props {
  books: OLDoc[];
}

function StarRating({ rating }: { rating: number }) {
  const rounded = Math.round(rating * 2) / 2;
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          size={12}
          className={i <= rounded ? "fill-[var(--primary)] text-[var(--primary)]" : "text-[var(--border)]"}
        />
      ))}
    </div>
  );
}

function BookSkeleton() {
  return (
    <div className="flex-shrink-0 w-44">
      <div className="skeleton w-44 h-64 rounded-xl mb-3" />
      <div className="skeleton h-3 w-24 mb-2" />
      <div className="skeleton h-4 w-36 mb-1" />
      <div className="skeleton h-3 w-20" />
    </div>
  );
}

export default function TrendingCarousel({ books }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (dir: "left" | "right") => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({ left: dir === "right" ? 300 : -300, behavior: "smooth" });
  };

  return (
    <section className="py-16 px-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 style={{ fontFamily: "'Merriweather', serif" }} className="text-3xl font-bold text-[var(--text)]">
            Trending Today
          </h2>
          <p className="text-[var(--secondary)] mt-1 text-sm">What readers are loving right now</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => scroll("left")}
            className="w-10 h-10 rounded-full border border-[var(--border)] flex items-center justify-center hover:bg-[var(--primary)] hover:text-[#111] hover:border-[var(--primary)] transition-all text-[var(--primary)]"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            onClick={() => scroll("right")}
            className="w-10 h-10 rounded-full border border-[var(--border)] flex items-center justify-center hover:bg-[var(--primary)] hover:text-[#111] hover:border-[var(--primary)] transition-all text-[var(--primary)]"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex gap-6 overflow-x-auto scrollbar-hide pb-8 -mx-6 px-6"
      >
        {books.length === 0
          ? Array.from({ length: 8 }).map((_, i) => <BookSkeleton key={i} />)
          : books.map((book, i) => (
            <motion.a
              key={book.key}
              href={`https://openlibrary.org${book.key}`}
              target="_blank"
              rel="noopener noreferrer"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06, duration: 0.4 }}
              whileHover={{ y: -8, transition: { duration: 0.2 } }}
              className="flex-shrink-0 w-44 group cursor-pointer"
            >
              {/* Cover */}
              <div className="relative w-44 h-64 rounded-xl overflow-hidden shadow-md group-hover:shadow-[0_16px_40px_rgba(0,0,0,0.4)] transition-shadow duration-300 mb-3 border border-[var(--border)]">
                {book.cover_i ? (
                  <img
                    src={getCoverUrl(book.cover_i, "M")}
                    alt={book.title}
                    className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                  />
                ) : (
                  <div className="w-full h-full bg-gradient-to-br from-[var(--card)] to-[var(--bg)] flex flex-col items-center justify-center p-4">
                    <span className="text-4xl mb-2">📖</span>
                    <span className="text-[var(--primary)] text-xs text-center font-medium leading-tight">{book.title}</span>
                  </div>
                )}
                {/* Genre tag */}
                {book.subject?.[0] && (
                  <div className="absolute top-2 left-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#111]/80 text-[var(--primary)] backdrop-blur-sm border border-[var(--primary)]/20">
                    {book.subject[0].slice(0, 18)}
                  </div>
                )}
              </div>
              {/* Stars */}
              <div className="flex items-center gap-1.5 mb-1">
                {book.ratings_average ? (
                  <>
                    <StarRating rating={book.ratings_average} />
                    <span className="text-xs text-[var(--secondary)]">{book.ratings_average.toFixed(1)}</span>
                  </>
                ) : (
                  <span className="text-xs text-[var(--border)]">No rating</span>
                )}
              </div>
              <h3 className="font-semibold text-[var(--text)] text-sm leading-tight line-clamp-2 mb-0.5 group-hover:text-[var(--primary)] transition-colors">
                {book.title}
              </h3>
              <p className="text-xs text-[var(--secondary)]">{book.author_name?.[0] ?? "Unknown"}</p>
            </motion.a>
          ))}
        {/* Spacer for proper right padding scroll */}
        <div className="flex-shrink-0 w-6" />
      </div>
    </section>
  );
}
