import { Card, Chip, LINK_CLASS, PageHeader } from "../components/ui";

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

export function DocsPage() {
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

        <pre className="min-w-0 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/80 p-4 text-xs leading-6 text-slate-300">
          <code>{`{
  "mcpServers": {
    "journal-scout": {
      "type": "http",
      "url": "${MCP_URL}"
    }
  }
}`}</code>
        </pre>
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
                className="rounded-md px-2 py-1.5 text-sm text-slate-400 transition-colors hover:bg-slate-800/70 hover:text-slate-100"
              >
                Alur kerja
              </a>
              {GROUPS.map((group) => (
                <a
                  key={group}
                  href={`#tools-${group.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
                  className="rounded-md px-2 py-1.5 text-sm text-slate-400 transition-colors hover:bg-slate-800/70 hover:text-slate-100"
                >
                  {group}
                </a>
              ))}
            </div>
          </nav>
        </aside>

        <main className="min-w-0 space-y-5">
          <Card id="workflow" className="space-y-4 p-4 sm:p-5">
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

          <div className="space-y-4">
            {GROUPS.map((group) => {
              const tools = TOOLS.filter((tool) => tool.group === group);
              const id = `tools-${group.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
              return (
                <section
                  key={group}
                  id={id}
                  aria-labelledby={`${id}-title`}
                  className="scroll-mt-4 overflow-hidden rounded-xl border border-slate-800 bg-slate-900/30"
                >
                  <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 sm:px-5">
                    <h2 id={`${id}-title`} className="text-sm font-semibold text-slate-100">
                      {group}
                    </h2>
                    <Chip variant="secondary">{tools.length} tools</Chip>
                  </div>
                  <dl className="divide-y divide-slate-800/80">
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
                </section>
              );
            })}
          </div>
        </main>
      </div>
    </div>
  );
}
