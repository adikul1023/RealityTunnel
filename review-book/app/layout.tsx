import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ReviewBook — Discover Your Next Favorite Book",
  description:
    "Explore millions of books across every genre. Browse trending titles, discover hidden gems, and find your next great read on ReviewBook.",
  keywords: "books, book reviews, reading, discover books, book recommendations",
  openGraph: {
    title: "ReviewBook — Discover Your Next Favorite Book",
    description: "Explore millions of books across every genre.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
