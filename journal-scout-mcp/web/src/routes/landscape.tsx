import { useMemo, useState } from "react";
import { fetchLandscape } from "../lib/api";
import type { LandscapeCluster, LandscapeNode, LandscapeResponse } from "../lib/types";
import {
  Alert,
  Button,
  Card,
  Input,
  PageHeader,
  Spinner,
  cn,
} from "../components/ui";

const CLUSTER_COLORS = [
  "#38bdf8",
  "#a78bfa",
  "#34d399",
  "#fbbf24",
  "#fb7185",
  "#22d3ee",
  "#f472b6",
  "#a3e635",
];

const WIDTH = 960;
const HEIGHT = 560;
const PADDING = 48;

function colorFor(cluster: number): string {
  return CLUSTER_COLORS[cluster % CLUSTER_COLORS.length];
}

function scaleNodes(nodes: LandscapeNode[]) {
  if (nodes.length === 0) return new Map<string, { x: number; y: number }>();
  const xs = nodes.map((node) => node.x);
  const ys = nodes.map((node) => node.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  return new Map(
    nodes.map((node) => [
      node.id,
      {
        x: PADDING + ((node.x - minX) / spanX) * (WIDTH - PADDING * 2),
        y: PADDING + ((node.y - minY) / spanY) * (HEIGHT - PADDING * 2),
      },
    ]),
  );
}

function clusterCentroids(
  nodes: LandscapeNode[],
  positions: Map<string, { x: number; y: number }>,
) {
  const buckets = new Map<number, { x: number; y: number; count: number }>();
  for (const node of nodes) {
    const position = positions.get(node.id);
    if (!position) continue;
    const bucket = buckets.get(node.cluster) ?? { x: 0, y: 0, count: 0 };
    bucket.x += position.x;
    bucket.y += position.y;
    bucket.count += 1;
    buckets.set(node.cluster, bucket);
  }
  return new Map(
    [...buckets.entries()].map(([cluster, bucket]) => [
      cluster,
      { x: bucket.x / bucket.count, y: bucket.y / bucket.count },
    ]),
  );
}

export function LandscapePage() {
  const [query, setQuery] = useState("");
  const [nClusters, setNClusters] = useState("");
  const [limit, setLimit] = useState("50");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LandscapeResponse | null>(null);
  const [activeCluster, setActiveCluster] = useState<number | null>(null);

  const positions = useMemo(() => scaleNodes(data?.nodes ?? []), [data]);
  const centroids = useMemo(
    () => clusterCentroids(data?.nodes ?? [], positions),
    [data, positions],
  );

  async function run() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setActiveCluster(null);
    try {
      const response = await fetchLandscape(query.trim(), {
        nClusters: nClusters ? Number(nClusters) : undefined,
        limitPerSource: limit ? Number(limit) : undefined,
      });
      setData(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Landscape request failed.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  const visibleClusters: LandscapeCluster[] = (data?.clusters ?? []).filter(
    (cluster) => activeCluster === null || cluster.id === activeCluster,
  );

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Research landscape"
        description="Turn a keyword into a clustered map of the literature. Clusters come from TF-IDF text similarity; labels from c-TF-IDF terms."
      />

      <Card className="flex flex-col gap-3 p-4">
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void run();
          }}
        >
          <label className="flex min-w-[260px] flex-1 flex-col gap-1 text-[12px] text-slate-400">
            Keyword or question
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="e.g. graph neural networks for drug discovery"
            />
          </label>
          <label className="flex w-28 flex-col gap-1 text-[12px] text-slate-400">
            Clusters
            <Input
              value={nClusters}
              onChange={(event) => setNClusters(event.target.value)}
              inputMode="numeric"
              placeholder="auto"
            />
          </label>
          <label className="flex w-28 flex-col gap-1 text-[12px] text-slate-400">
            Per source
            <Input
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
              inputMode="numeric"
              placeholder="50"
            />
          </label>
          <Button type="submit" variant="primary" disabled={loading || !query.trim()}>
            {loading ? <Spinner size="xs" /> : null}
            Build map
          </Button>
        </form>
        {error ? <Alert tone="error">{error}</Alert> : null}
      </Card>

      {data ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
          <Card className="overflow-hidden p-0">
            <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2 text-[12px] text-slate-400">
              <span>
                {data.stats.papers} papers · {data.stats.clusters} clusters ·{" "}
                {data.stats.terms} terms
              </span>
              {activeCluster !== null ? (
                <button
                  type="button"
                  className="text-sky-300 hover:text-sky-200"
                  onClick={() => setActiveCluster(null)}
                >
                  Clear filter
                </button>
              ) : null}
            </div>
            <svg
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              className="block w-full"
              role="img"
              aria-label="Research landscape map"
            >
              <rect width={WIDTH} height={HEIGHT} fill="transparent" />
              {(data.nodes ?? []).map((node) => {
                const position = positions.get(node.id);
                if (!position) return null;
                const dimmed =
                  activeCluster !== null && node.cluster !== activeCluster;
                return (
                  <circle
                    key={node.id}
                    cx={position.x}
                    cy={position.y}
                    r={dimmed ? 3 : 5}
                    fill={colorFor(node.cluster)}
                    opacity={dimmed ? 0.18 : 0.9}
                    stroke={dimmed ? "none" : "#0f172a"}
                    strokeWidth={1}
                  >
                    <title>{`${node.title}${node.year ? ` (${node.year})` : ""}`}</title>
                  </circle>
                );
              })}
              {[...centroids.entries()].map(([cluster, point]) => {
                const label = (data.clusters ?? []).find((item) => item.id === cluster);
                if (!label) return null;
                const dimmed = activeCluster !== null && cluster !== activeCluster;
                return (
                  <text
                    key={`label-${cluster}`}
                    x={point.x}
                    y={point.y - 12}
                    textAnchor="middle"
                    fontSize={12}
                    fontWeight={600}
                    fill={dimmed ? "#334155" : colorFor(cluster)}
                  >
                    {label.label}
                  </text>
                );
              })}
            </svg>
          </Card>

          <div className="flex flex-col gap-2">
            {(data.clusters ?? []).map((cluster) => (
              <button
                key={cluster.id}
                type="button"
                onClick={() =>
                  setActiveCluster(activeCluster === cluster.id ? null : cluster.id)
                }
                className={cn(
                  "rounded-lg border p-3 text-left transition-colors",
                  activeCluster === cluster.id
                    ? "border-sky-500/60 bg-sky-500/10"
                    : "border-slate-800 bg-slate-900/40 hover:border-slate-700",
                )}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: colorFor(cluster.id) }}
                  />
                  <span className="text-[13px] font-semibold text-slate-100">
                    {cluster.label}
                  </span>
                </div>
                <div className="mt-1 text-[11px] text-slate-400">
                  {cluster.size} papers · median {Math.round(cluster.median_year)}
                </div>
                {cluster.top_topics.length > 0 ? (
                  <div className="mt-1 line-clamp-2 text-[11px] text-slate-500">
                    {cluster.top_topics.join(" · ")}
                  </div>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {!data && !loading && !error ? (
        <Card className="p-6 text-[13px] text-slate-400">
          Enter a keyword to generate a map. Similar papers group into clusters;
          each cluster is named from its most distinctive terms.
        </Card>
      ) : null}

      {data && visibleClusters.length === 0 ? (
        <Card className="p-4 text-[13px] text-slate-400">No papers matched.</Card>
      ) : null}
    </div>
  );
}
