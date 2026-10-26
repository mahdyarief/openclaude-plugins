import { PaperDrawer } from "../components/PaperDrawer";
import { SearchForm } from "../components/search/SearchForm";
import { SearchResults } from "../components/search/SearchResults";
import { Alert, LoadingLine, PageHeader } from "../components/ui";
import { useSearchController } from "../hooks/useSearchController";

export function SearchPage() {
  const controller = useSearchController();
  const { data, error, loading, drawerPaper, setDrawerPaper } = controller;

  return (
    <div className="w-full space-y-5">
      <PageHeader
        title="Literature search"
        description="One query fans out across Scopus, arXiv, OpenAlex, Semantic Scholar, Crossref, PubMed, DBLP and Garuda, then duplicate records are merged DOI-first into a single result set."
      />

      <SearchForm controller={controller} />

      {error && <Alert>{error}</Alert>}

      {loading && (
        <LoadingLine>Searching across providers, then merging duplicates…</LoadingLine>
      )}

      {data && <SearchResults controller={controller} />}

      <PaperDrawer paper={drawerPaper} onClose={() => setDrawerPaper(null)} />
    </div>
  );
}
