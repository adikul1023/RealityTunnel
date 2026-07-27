"use client";

import { motion } from "framer-motion";
import { Star, ArrowRight } from "lucide-react";
import { STAFF_PICKS, getCoverUrl } from "@/app/lib/openlibrary";

function StaffPickCard({
  pick,
  index,
}: {
  pick: (typeof STAFF_PICKS)[0];
  index: number;
}) {
  const olCoverUrl = getCoverUrl(pick.cover_i, "L");

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ delay: index * 0.1, duration: 0.5 }}
      className="group relative bg-[var(--card)] rounded-2xl overflow-hidden border border-[var(--border)] shadow-sm hover:shadow-[0_20px_60px_rgba(0,0,0,0.3)] transition-all duration-300 hover:-translate-y-1 flex flex-col"
    >
      {/* Staff pick badge */}
      <div className="absolute top-4 right-4 z-10 px-3 py-1 rounded-full bg-[var(--primary)] text-[#111] text-[10px] font-bold tracking-widest uppercase shadow-sm">
        Staff Pick
      </div>

      {/* Cover */}
      <div className="relative h-72 overflow-hidden bg-[var(--bg)]">
        <img
          src={olCoverUrl}
          alt={pick.title}
          className="w-full h-full object-cover object-top transition-transform duration-500 group-hover:scale-105"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
      </div>

      {/* Content */}
      <div className="p-6 flex flex-col flex-1">
        {/* Genre tag */}
        <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-[var(--primary)]/10 text-[var(--primary)] mb-3 self-start">
          {pick.genre}
        </span>

        <h3
          style={{ fontFamily: "'Merriweather', serif" }}
          className="text-xl font-bold text-[var(--text)] leading-snug mb-1"
        >
          {pick.title}
        </h3>
        <p className="text-sm text-[var(--secondary)] mb-3">{pick.author}</p>

        {/* Stars */}
        <div className="flex items-center gap-1 mb-4">
          {[1, 2, 3, 4].map((i) => (
            <Star key={i} size={14} className="fill-[var(--primary)] text-[var(--primary)]" />
          ))}
          <Star size={14} className="text-[var(--border)]" />
        </div>

        {/* Quote */}
        <blockquote className="text-sm text-[var(--secondary)] italic leading-relaxed border-l-2 border-[var(--primary)] pl-3 mb-5 flex-1">
          "{pick.quote}"
        </blockquote>

        {/* CTA */}
        <a
          href={`https://openlibrary.org${pick.key}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-sm font-semibold text-[var(--primary)] hover:gap-3 transition-all duration-200 group/link"
        >
          Read More
          <ArrowRight size={16} className="transition-transform group-hover/link:translate-x-1" />
        </a>
      </div>
    </motion.div>
  );
}

export default function StaffPicks() {
  return (
    <section className="py-16 px-6 max-w-7xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="mb-10"
      >
        <h2
          style={{ fontFamily: "'Merriweather', serif" }}
          className="text-3xl font-bold text-[var(--text)]"
        >
          Staff Picks
        </h2>
        <p className="text-[var(--secondary)] mt-1 text-sm">Hand-selected reads from our editors</p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {STAFF_PICKS.map((pick, i) => (
          <StaffPickCard key={pick.key} pick={pick} index={i} />
        ))}
      </div>
    </section>
  );
}
