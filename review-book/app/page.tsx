import { getTrendingBooks } from "@/app/lib/openlibrary";
import HomepageClient from "@/app/components/HomepageClient";

export default async function Home() {
  const trending = await getTrendingBooks();

  return <HomepageClient trending={trending} />;
}
