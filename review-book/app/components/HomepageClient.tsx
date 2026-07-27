"use client";

import { useState } from "react";
import { OLDoc } from "@/app/lib/openlibrary";
import Hero from "@/app/components/Hero";
import TrendingCarousel from "@/app/components/TrendingCarousel";
import GenrePills from "@/app/components/GenrePills";
import StaffPicks from "@/app/components/StaffPicks";
import RecentlyAdded from "@/app/components/RecentlyAdded";
import Statistics from "@/app/components/Statistics";
import Footer from "@/app/components/Footer";

interface Props {
  trending: OLDoc[];
}

export default function HomepageClient({ trending }: Props) {
  const [selectedGenre, setSelectedGenre] = useState<string | null>(null);

  return (
    <main style={{ backgroundColor: "var(--bg)", minHeight: "100vh" }}>
      <Hero />
      <TrendingCarousel books={trending} />
      <GenrePills selected={selectedGenre} onSelect={setSelectedGenre} />
      <StaffPicks />
      <RecentlyAdded genre={selectedGenre} />
      <Statistics />
      <Footer />
    </main>
  );
}
