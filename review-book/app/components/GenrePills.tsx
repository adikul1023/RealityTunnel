"use client";

import { motion } from "framer-motion";
import { GENRES } from "@/app/lib/openlibrary";

const GENRE_ICONS: Record<string, string> = {
  "Fantasy": "🧙",
  "Sci-Fi": "🚀",
  "Mystery": "🔍",
  "Romance": "💌",
  "Programming": "💻",
  "History": "📜",
  "Manga": "🎌",
  "Biography": "👤",
  "Horror": "👻",
  "Thriller": "🔪",
  "Poetry": "🪶",
  "Self-Help": "🌱",
};

interface Props {
  selected: string | null;
  onSelect: (genre: string | null) => void;
}

export default function GenrePills({ selected, onSelect }: Props) {
  return (
    <section className="py-10 px-6 max-w-7xl mx-auto">
      <motion.h2
        initial={{ opacity: 0, x: -20 }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        style={{ fontFamily: "'Merriweather', serif" }}
        className="text-3xl font-bold text-[#222222] mb-6"
      >
        Popular Genres
      </motion.h2>
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true }}
        variants={{
          hidden: {},
          visible: { transition: { staggerChildren: 0.05 } },
        }}
        className="flex flex-wrap gap-3"
      >
        <motion.button
          variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0 } }}
          onClick={() => onSelect(null)}
          className={`px-5 py-2.5 rounded-full text-sm font-semibold border transition-all duration-200 ${
            selected === null
              ? "bg-[var(--primary)] text-[#111] border-[var(--primary)] shadow-[0_0_15px_rgba(217,182,125,0.4)]"
              : "bg-transparent text-[var(--text)] border-[var(--border)] hover:border-[var(--primary)] hover:text-[var(--primary)]"
          }`}
        >
          All Books
        </motion.button>
        {GENRES.map((genre) => (
          <motion.button
            key={genre}
            variants={{ hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0 } }}
            onClick={() => onSelect(genre === selected ? null : genre)}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold border transition-all duration-200 ${
              selected === genre
                ? "bg-[var(--primary)] text-[#111] border-[var(--primary)] shadow-[0_0_15px_rgba(217,182,125,0.4)]"
                : "bg-[var(--card)] text-[var(--secondary)] border-[var(--border)] hover:border-[var(--primary)] hover:text-[var(--primary)]"
            }`}
          >
            <span>{GENRE_ICONS[genre] ?? "📚"}</span>
            {genre}
          </motion.button>
        ))}
      </motion.div>
    </section>
  );
}
