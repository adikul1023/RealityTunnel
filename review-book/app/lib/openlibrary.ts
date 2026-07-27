// Open Library API helpers

export const OL_BASE = "https://openlibrary.org";
export const OL_COVERS = "https://covers.openlibrary.org";

export interface OLBook {
  key: string;
  title: string;
  author_name?: string[];
  cover_i?: number;
  subject?: string[];
  first_publish_year?: number;
  number_of_pages_median?: number;
  language?: string[];
  ratings_average?: number;
  ratings_count?: number;
  edition_count?: number;
}

export interface OLDoc {
  key: string;
  title: string;
  author_name?: string[];
  cover_i?: number;
  subject?: string[];
  first_publish_year?: number;
  number_of_pages_median?: number;
  language?: string[];
  ratings_average?: number;
  ratings_count?: number;
}

export function getCoverUrl(coverId: number, size: "S" | "M" | "L" = "M"): string {
  return `${OL_COVERS}/b/id/${coverId}-${size}.jpg`;
}

export function getGoodreadsSearchUrl(title: string, author?: string): string {
  const query = encodeURIComponent(`${title} ${author ?? ""}`.trim());
  return `https://www.goodreads.com/search?q=${query}`;
}

export async function searchBooks(query: string, limit = 10, offset = 0): Promise<OLDoc[]> {
  const res = await fetch(
    `${OL_BASE}/search.json?q=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}&fields=key,title,author_name,cover_i,subject,first_publish_year,number_of_pages_median,language,ratings_average,ratings_count`,
    { next: { revalidate: 300 } }
  );
  if (!res.ok) return [];
  const data = await res.json();
  return (data.docs ?? []) as OLDoc[];
}

export async function getTrendingBooks(): Promise<OLDoc[]> {
  // Use the trending/daily endpoint from Open Library
  const res = await fetch(`${OL_BASE}/trending/daily.json?limit=12`, {
    next: { revalidate: 3600 },
  });
  if (!res.ok) {
    // fallback: search for popular books
    return searchBooks("fiction bestseller", 12);
  }
  const data = await res.json();
  const works = (data.works ?? []) as OLDoc[];
  return works;
}

export async function getBooksBySubject(subject: string, limit = 8, offset = 0): Promise<OLDoc[]> {
  const res = await fetch(
    `${OL_BASE}/subjects/${encodeURIComponent(subject.toLowerCase().replace(/ /g, "_"))}.json?limit=${limit}&offset=${offset}`,
    { next: { revalidate: 3600 } }
  );
  if (!res.ok) return searchBooks(subject, limit, offset);
  const data = await res.json();
  // subject API returns works with slightly different shape
  const works = (data.works ?? []) as Array<{
    key: string;
    title: string;
    authors?: Array<{ name: string }>;
    cover_id?: number;
    first_publish_year?: number;
    subject?: string[];
  }>;
  return works.map((w) => ({
    key: w.key,
    title: w.title,
    author_name: w.authors?.map((a) => a.name),
    cover_i: w.cover_id,
    subject: w.subject,
    first_publish_year: w.first_publish_year,
  }));
}

// Staff picks — curated popular work keys on Open Library
export const STAFF_PICKS = [
  { key: "/works/OL893415W", cover_i: 10480397, title: "The Name of the Wind", author: "Patrick Rothfuss", quote: "One of the finest fantasy novels written in the last decade.", genre: "Fantasy" },
  { key: "/works/OL82592W",  cover_i: 10552348, title: "Dune",                 author: "Frank Herbert",    quote: "A masterwork of science fiction. Dense, intelligent, essential.", genre: "Sci-Fi" },
  { key: "/works/OL45804W",  cover_i: 15358738, title: "1984",                 author: "George Orwell",    quote: "Chilling, prescient and more relevant than ever.", genre: "Dystopian" },
  { key: "/works/OL27479W",  cover_i: 10476834, title: "To Kill a Mockingbird",author: "Harper Lee",       quote: "A story of enduring warmth and humor despite injustice.", genre: "Classic" },
];

export const GENRES = [
  "Fantasy", "Sci-Fi", "Mystery", "Romance",
  "Programming", "History", "Manga", "Biography",
  "Horror", "Thriller", "Poetry", "Self-Help",
];
