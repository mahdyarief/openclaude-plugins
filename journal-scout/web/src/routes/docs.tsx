import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Card, Chip, cn, Input, LINK_CLASS, PageHeader } from "../components/ui";
import { Check, ChevronDown, Copy } from "lucide-react";

type ToolEntry = {
  name: string;
  purpose: string;
  group: "Search" | "Papers" | "Graph & metrics" | "Export & archive" | "Review (SLR)" | "Keys";
};

const MCP_URL =
  typeof window === "undefined"
    ? "/mcp"
    : `${window.location.origin}/mcp`;

const TOOLS: ToolEntry[] = [
  { name: "search_all", group: "Search", purpose: "Cari semua sumber secara paralel lalu gabungkan duplikat berdasarkan DOI/judul." },
  { name: "search_author", group: "Search", purpose: "Cari semua paper dari satu penulis lintas sumber (Scopus, Crossref, OpenAlex, arXiv), lalu digabung dan dideduplikasi." },
  { name: "search_scopus", group: "Search", purpose: "Cari hanya di Scopus." },
  { name: "search_arxiv", group: "Search", purpose: "Cari hanya di arXiv." },
  { name: "search_openalex", group: "Search", purpose: "Cari hanya di OpenAlex." },
  { name: "search_crossref", group: "Search", purpose: "Cari hanya di Crossref." },
  { name: "search_pubmed", group: "Search", purpose: "Cari hanya di PubMed." },
  { name: "search_garuda", group: "Search", purpose: "Cari hanya di Garuda." },
  { name: "search_consensus", group: "Search", purpose: "Cari hanya di Consensus." },
  { name: "search_exa", group: "Search", purpose: "Cari web melalui Exa (endpoint MCP publik; tidak perlu API key)." },
  { name: "search_corpus", group: "Search", purpose: "Cari teks (judul, abstrak, venue, penulis, kata kunci) pada hasil pencarian yang sudah diarsipkan lokal — tanpa request jaringan." },
  { name: "get_paper", group: "Papers", purpose: "Ambil satu paper berdasarkan DOI / id arXiv / Scopus / OpenAlex, gabungkan metadata, dan lampirkan tautan akses terbuka." },
  { name: "get_paper_abstract", group: "Papers", purpose: "Cari abstrak satu paper (berdasarkan DOI, identifier lain, atau judul) dari semua sumber yang bisa menjawab. Mengembalikan status not_found dan abstrak null bila tidak ada — tidak menebak dari judul." },
  { name: "get_abstracts", group: "Papers", purpose: "Isi abstrak yang kosong pada daftar paper (misalnya hasil search_all). Urutan tetap, abstrak yang sudah ada tidak ditimpa, dan status tiap paper dilaporkan." },
  { name: "get_references", group: "Graph & metrics", purpose: "Kumpulkan daftar referensi satu paper dari semua sumber yang menyediakannya (Scopus/OpenAlex/Crossref/OpenCitations), digabung dan dideduplikasi." },
  { name: "get_citations", group: "Graph & metrics", purpose: "Kumpulkan paper yang mengutip satu paper lintas sumber (Scopus + OpenAlex + OpenCitations)." },
  { name: "get_related_works", group: "Graph & metrics", purpose: "Tampilkan paper terkait menurut OpenAlex (mirip fitur Related Works di Publish or Perish), digabung dan dideduplikasi." },
  { name: "build_citation_network", group: "Graph & metrics", purpose: "Bangun jaringan sitasi di sekitar satu paper: kutipan langsung, bibliographic coupling, dan co-citation. graph_format=graphml menghasilkan berkas untuk Gephi/VOSviewer." },
  { name: "build_research_landscape", group: "Graph & metrics", purpose: "Cari kata kunci lalu kelompokkan korpus hasil menjadi peta riset: klaster TF-IDF, label c-TF-IDF, koordinat 2D, serta statistik topik/penulis/venue per klaster." },
  { name: "compute_metrics", group: "Graph & metrics", purpose: "Hitung metrik ala Publish or Perish (jumlah paper, total sitasi, h-index, i10, g-index, kecepatan sitasi) untuk nama penulis atau query." },
  { name: "get_abstract_details", group: "Keys", purpose: "Detail abstrak Scopus untuk Scopus id." },
  { name: "get_author_profile", group: "Keys", purpose: "Profil penulis dari Scopus." },
  { name: "get_quota_status", group: "Keys", purpose: "Batas laju dan status kuota setiap sumber yang terkonfigurasi, termasuk header Scopus langsung bila tersedia." },
  { name: "scival_author_metrics", group: "Keys", purpose: "Metrik penulis dari SciVal." },
  { name: "scival_institution_metrics", group: "Keys", purpose: "Metrik institusi dari SciVal." },
  { name: "scival_author_lookup", group: "Keys", purpose: "Cari penulis di SciVal berdasarkan nama." },
  { name: "scival_institution_lookup", group: "Keys", purpose: "Cari institusi di SciVal berdasarkan nama." },
  { name: "scival_topic_metrics", group: "Keys", purpose: "Metrik topik dari SciVal." },
  { name: "rotate_consensus_key", group: "Keys", purpose: "Verifikasi kunci Consensus baru ke API; hanya disimpan bila diterima. Kunci lama tetap aman bila verifikasi gagal." },
  { name: "export_results", group: "Export & archive", purpose: "Ekspor daftar paper ke BibTeX, RIS, CSV, EndNote, WoS, gaya sitasi, atau JSON." },
  { name: "identify_paper", group: "Export & archive", purpose: "Kenali paper dari berkas PDF lokal dengan resolusi DOI atau judul." },
  { name: "check_watches", group: "Export & archive", purpose: "Jalankan semua watch pencarian tersimpan dan kembalikan paper yang belum pernah dilaporkan." },
  { name: "slr_import", group: "Review (SLR)", purpose: "Impor catatan ke state review SLR (dedup berdasarkan DOI lalu judul) dari hasil pencarian." },
  { name: "slr_screen", group: "Review (SLR)", purpose: "Catat keputusan screening judul/abstrak untuk satu catatan: include/exclude/unclear disertai kode alasan." },
  { name: "slr_full_text", group: "Review (SLR)", purpose: "Catat keputusan kelayakan full-text untuk satu catatan: include/exclude disertai alasan." },
  { name: "slr_appraise", group: "Review (SLR)", purpose: "Catat penilaian kualitas studi yang termasuk: kelas, butir Y/T, dan risiko." },
  { name: "slr_extract", group: "Review (SLR)", purpose: "Simpan field ekstraksi (tahun, metrik, dll.) untuk studi yang termasuk." },
  { name: "slr_prisma", group: "Review (SLR)", purpose: "Hitung alur PRISMA 2020 dari state review saat ini." },
  { name: "slr_summary", group: "Review (SLR)", purpose: "Snapshot SLR lengkap (PRISMA + keputusan tiap catatan), atau CSV dengan format=csv." },
  { name: "slr_reset", group: "Review (SLR)", purpose: "Hapus seluruh state review SLR." },
];

const GROUPS: ToolEntry["group"][] = [
  "Search",
  "Papers",
  "Graph & metrics",
  "Export & archive",
  "Review (SLR)",
  "Keys",
];

const DEFAULT_OPEN_GROUPS: Record<ToolEntry["group"], boolean> = {
  Search: true,
  Papers: true,
  "Graph & metrics": false,
  "Export & archive": false,
  "Review (SLR)": false,
  Keys: false,
};

const CONFIG_SNIPPET = `{
  "mcpServers": {
    "journal-scout": {
      "type": "http",
      "url": "${MCP_URL}"
    }
  }
}`;

function filterTools(query: string) {
  const normalized = query.trim().toLocaleLowerCase();
  return GROUPS.map((group) => ({
    group,
    tools: TOOLS.filter((tool) => {
      if (tool.group !== group) return false;
      if (!normalized) return true;
      if (group.toLocaleLowerCase().includes(normalized)) return true;
      return [tool.name, tool.purpose].some((value) =>
        value.toLocaleLowerCase().includes(normalized),
      );
    }),
  })).filter(({ tools }) => tools.length > 0);
}

function CopySnippetButton({ snippet }: { snippet: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      className="absolute right-2 top-2"
      aria-label={copied ? "Snippet disalin" : "Salin konfigurasi MCP"}
      onClick={handleCopy}
    >
      {copied ? <Check aria-hidden="true" className="h-3.5 w-3.5" /> : <Copy aria-hidden="true" className="h-3.5 w-3.5" />}
      {copied ? "Tersalin" : "Salin"}
    </Button>
  );
}

export function DocsPage() {
  const [query, setQuery] = useState("");
  const groups = useMemo(() => filterTools(query), [query]);
  const [openGroups, setOpenGroups] = useState(DEFAULT_OPEN_GROUPS);
  const [activeId, setActiveId] = useState("workflow");
  const searching = query.trim().length > 0;

  useEffect(() => {
    const updateActive = () => {
      const sections = Array.from(document.querySelectorAll<HTMLElement>("main [data-docs-section]"))
        .map((element) => ({
          id: element.id,
          top: element.getBoundingClientRect().top,
          bottom: element.getBoundingClientRect().bottom,
        }))
        .filter(({ top, bottom }) => top < window.innerHeight && bottom > 0)
        .sort((a, b) => a.top - b.top);
      if (!sections.length) return;
      const passed = sections.filter(({ top }) => top <= 96);
      const atPageEnd =
        window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;
      const current = atPageEnd ? sections.at(-1) : (passed.at(-1) ?? sections[0]);
      if (current) setActiveId((prev) => (prev === current.id ? prev : current.id));
    };
    window.addEventListener("scroll", updateActive, { passive: true });
    window.addEventListener("resize", updateActive);
    updateActive();
    return () => {
      window.removeEventListener("scroll", updateActive);
      window.removeEventListener("resize", updateActive);
    };
  }, []);

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <PageHeader
        title="Dokumentasi MCP"
        description="Hubungkan klien MCP ke journal-scout dan gunakan tools untuk mencari, menelusuri, serta mengekspor literatur."
      />

      <section
        aria-labelledby="connection-title"
        className="grid grid-cols-1 gap-4 overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.9fr)] lg:items-center"
      >
        <div className="min-w-0 space-y-3">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400" aria-hidden="true" />
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-emerald-300">
              Streamable HTTP
            </p>
          </div>
          <div>
            <h2 id="connection-title" className="text-lg font-semibold tracking-tight text-slate-100">
              Hubungkan klien MCP
            </h2>
            <p className="mt-1.5 max-w-xl text-sm leading-6 text-slate-400">
              Gunakan endpoint di bawah. Untuk deployment yang mengaktifkan{" "}
              <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-200">
                JOSC_MCP_TOKEN
              </code>
              , tambahkan bearer token ke konfigurasi klien.
            </p>
          </div>
          <a className={LINK_CLASS} href="/healthz" target="_blank" rel="noreferrer">
            Periksa status server <span aria-hidden="true">↗</span>
          </a>
        </div>

        <div className="relative min-w-0">
          <CopySnippetButton snippet={CONFIG_SNIPPET} />
          <pre className="min-w-0 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/80 p-4 pt-12 text-xs leading-6 text-slate-300">
            <code>{CONFIG_SNIPPET}</code>
          </pre>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <aside className="min-w-0 lg:sticky lg:top-4 lg:self-start">
          <nav
            aria-label="Navigasi dokumentasi"
            className="rounded-xl border border-slate-800 bg-slate-900/30 p-3"
          >
            <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              Di halaman ini
            </p>
            <div className="flex flex-wrap gap-1 lg:flex-col lg:flex-nowrap">
              <a
                href="#workflow"
                aria-current={activeId === "workflow" ? "location" : undefined}
                onClick={() => setActiveId("workflow")}
                className={cn(
                  "rounded-md px-2 py-1.5 text-sm transition-colors",
                  activeId === "workflow" ? "bg-slate-800/70 text-slate-100" : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-100",
                )}
              >
                Alur kerja
              </a>
              {GROUPS.map((group) => {
                const id = `tools-${group.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
                return (
                  <a
                    key={group}
                    href={`#${id}`}
                    aria-current={activeId === id ? "location" : undefined}
                    onClick={() => {
                      setActiveId(id);
                      setOpenGroups((current) => ({ ...current, [group]: true }));
                    }}
                    className={cn(
                      "rounded-md px-2 py-1.5 text-sm transition-colors",
                      activeId === id ? "bg-slate-800/70 text-slate-100" : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-100",
                    )}
                  >
                    {group}
                  </a>
                );
              })}
            </div>
          </nav>
        </aside>

        <main className="min-w-0 space-y-5">
          <Card id="workflow" data-docs-section className="scroll-mt-14 space-y-4 p-4 sm:p-5">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-sky-300">
                Mulai di sini
              </p>
              <h2 className="mt-1 text-base font-semibold text-slate-100">Alur riset yang umum</h2>
            </div>
            <ol className="grid gap-3 sm:grid-cols-3">
              <li className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <span className="text-xs font-medium text-slate-500">01</span>
                <p className="mt-2 text-sm text-slate-300">
                  Cari lintas sumber dengan <code className="text-sky-300">search_all</code> dan operator boolean huruf besar, misalnya <code className="text-slate-200">insurance AND AI</code>.
                </p>
              </li>
              <li className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <span className="text-xs font-medium text-slate-500">02</span>
                <p className="mt-2 text-sm text-slate-300">
                  Lengkapi abstrak yang kosong memakai <code className="text-sky-300">get_abstracts</code>.
                </p>
              </li>
              <li className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <span className="text-xs font-medium text-slate-500">03</span>
                <p className="mt-2 text-sm text-slate-300">
                  Telusuri sitasi, lalu ekspor pustaka dengan <code className="text-sky-300">export_results</code>.
                </p>
              </li>
            </ol>
            <p className="border-t border-slate-800 pt-3 text-xs leading-5 text-slate-400">
              Periksa <code className="text-slate-300">errors</code> pada respons. Kegagalan satu sumber tidak menghentikan pencarian, tetapi hasilnya mungkin tidak lengkap.
            </p>
          </Card>

          <section aria-label="Daftar tools" className="space-y-4">
            <div className="space-y-3">
              <Input
                aria-label="Cari tool"
                placeholder="Cari tool berdasarkan nama, deskripsi, atau grup…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              {groups.length === 0 && (
                <p role="status" className="text-sm text-slate-400">
                  Tidak ada tool yang cocok dengan “{query.trim()}”.{" "}
                  <button type="button" className={LINK_CLASS} onClick={() => setQuery("")}>
                    Hapus pencarian
                  </button>
                </p>
              )}
            </div>
            {groups.map(({ group, tools }) => {
              const id = `tools-${group.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
              const expanded = searching || openGroups[group];
              return (
                <section
                  key={group}
                  id={id}
                  data-docs-section
                  aria-labelledby={`${id}-title`}
                  className="scroll-mt-14 overflow-hidden rounded-xl border border-slate-800 bg-slate-900/30"
                >
                  <div className="border-b border-slate-800 px-4 py-3 sm:px-5">
                    <h2 id={`${id}-title`} className="w-full">
                      <button
                        type="button"
                        aria-expanded={expanded}
                        aria-controls={`${id}-list`}
                        onClick={() => setOpenGroups((current) => ({ ...current, [group]: !current[group] }))}
                        className="flex w-full items-center justify-between gap-3 rounded text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          <ChevronDown
                            aria-hidden="true"
                            className={cn("h-4 w-4 shrink-0 transition-transform", !expanded && "-rotate-90")}
                          />
                          <span className="text-sm font-semibold text-slate-100">{group}</span>
                        </span>
                        <Chip variant="secondary">{tools.length} tools</Chip>
                      </button>
                    </h2>
                  </div>
                  {expanded && (
                    <dl id={`${id}-list`} className="divide-y divide-slate-800/80">
                      {tools.map((tool) => (
                        <div
                          key={tool.name}
                          className="grid gap-1.5 px-4 py-3 sm:grid-cols-[minmax(10rem,0.32fr)_minmax(0,1fr)] sm:gap-5 sm:px-5"
                        >
                          <dt>
                            <code className="break-all rounded bg-slate-800/70 px-1.5 py-1 text-xs font-medium text-sky-200">
                              {tool.name}
                            </code>
                          </dt>
                          <dd className="text-sm leading-6 text-slate-400">{tool.purpose}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </section>
              );
            })}
          </section>
        </main>
      </div>
    </div>
  );
}
