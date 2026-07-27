"use client";

import { useRef, useEffect, useState } from "react";
import { motion, useInView, useMotionValue, useSpring } from "framer-motion";

function AnimatedNumber({ target, suffix = "" }: { target: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const raw = useMotionValue(0);
  const spring = useSpring(raw, { stiffness: 50, damping: 18 });
  const [display, setDisplay] = useState("0");

  useEffect(() => {
    if (inView) raw.set(target);
  }, [inView, raw, target]);

  useEffect(() => {
    return spring.on("change", (v) => {
      if (target >= 1_000_000) {
        setDisplay((v / 1_000_000).toFixed(0) + "M");
      } else if (target >= 1_000) {
        setDisplay((v / 1_000).toFixed(0) + "K");
      } else {
        setDisplay(Math.round(v).toString());
      }
    });
  }, [spring, target]);

  return <span ref={ref}>{display}{suffix}</span>;
}

const STATS = [
  { value: 10_000_000, label: "Books Indexed", icon: "📚", suffix: "+" },
  { value: 500,        label: "Genres",         icon: "🗂️", suffix: "+" },
  { value: 100,        label: "Languages",       icon: "🌍", suffix: "+" },
  { value: 6_000_000,  label: "Authors",         icon: "✍️", suffix: "+" },
];

export default function Statistics() {
  return (
    <section className="py-20 px-6 relative overflow-hidden border-y border-[var(--border)] bg-[var(--card)]">
      {/* Background */}
      <div className="paper-texture absolute inset-0 opacity-20" />
      <div className="absolute top-0 right-0 w-96 h-96 rounded-full bg-[var(--primary)]/10 blur-3xl" />

      <div className="relative z-10 max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-14"
        >
          <h2 style={{ fontFamily: "'Merriweather', serif" }} className="text-3xl font-bold text-[var(--text)] mb-2">
            The World's Books, in One Place
          </h2>
          <p className="text-[var(--secondary)] text-sm">Powered by Open Library — free and open forever</p>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          {STATS.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1, duration: 0.5 }}
              className="text-center"
            >
              <div className="text-4xl mb-3">{stat.icon}</div>
              <div
                style={{ fontFamily: "'Merriweather', serif" }}
                className="text-4xl font-black text-[var(--text)] mb-1"
              >
                <AnimatedNumber target={stat.value} suffix={stat.suffix} />
              </div>
              <p className="text-[#D9B67D]/80 text-sm font-medium">{stat.label}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
