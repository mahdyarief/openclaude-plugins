import { useEffect, useRef } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import type { GraphEdge, GraphNode } from "../lib/types";

const WIDTH = 1000;
const HEIGHT = 700;

type SimNode = GraphNode & SimulationNodeDatum;
type SimLink = SimulationLinkDatum<SimNode> & {
  type: GraphEdge["type"];
  weight: number;
};

// Canvas cannot resolve CSS custom properties, so token names are read back
// through getComputedStyle at draw time (see cssVar below).
const KIND_COLOR: Record<GraphNode["kind"], string> = {
  seed: "--color-graph-seed",
  citation: "--color-graph-citation",
  reference: "--color-graph-reference",
  cocited: "--color-graph-cocited",
};

const EDGE_STYLE: Record<
  GraphEdge["type"],
  { stroke: string; dash: number[]; opacity: number }
> = {
  cites: { stroke: "--color-edge-cites", dash: [], opacity: 0.75 },
  coupled: { stroke: "--color-edge-coupled", dash: [5, 4], opacity: 0.6 },
  cocited: { stroke: "--color-edge-cocited", dash: [2, 4], opacity: 0.5 },
};

function cssVar(canvas: HTMLCanvasElement, name: string): string {
  const value = getComputedStyle(canvas).getPropertyValue(name).trim();
  return value || "#888";
}

function radius(node: GraphNode): number {
  if (node.kind === "seed") return 13;
  const citations = node.citation_count ?? 0;
  return Math.min(11, 5 + Math.sqrt(citations) * 0.5);
}

export function ForceGraph({
  nodes,
  edges,
  selectedId,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const drawRef = useRef<() => void>(() => {});
  const selectedRef = useRef<string | null>(selectedId);
  const sizeRef = useRef({ width: WIDTH, height: HEIGHT, dpr: 1 });

  useEffect(() => {
    selectedRef.current = selectedId;
    drawRef.current();
  }, [selectedId]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      sizeRef.current = { width: rect.width, height: rect.height, dpr };
    };
    resize();
    const observer = new ResizeObserver(() => {
      resize();
      drawRef.current();
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const simNodes: SimNode[] = nodes.map((node) => ({ ...node }));
    const byId = new Map(simNodes.map((node) => [node.id, node]));
    const simLinks: SimLink[] = edges
      .filter((edge) => byId.has(edge.source) && byId.has(edge.target))
      .map((edge) => ({ ...edge }));

    nodesRef.current = simNodes;

    const colors = {
      seed: cssVar(canvas, KIND_COLOR.seed),
      citation: cssVar(canvas, KIND_COLOR.citation),
      reference: cssVar(canvas, KIND_COLOR.reference),
      cocited: cssVar(canvas, KIND_COLOR.cocited),
      ink: cssVar(canvas, "--color-ink"),
      nodeStroke: cssVar(canvas, "--color-node-stroke"),
      edge: {
        cites: cssVar(canvas, EDGE_STYLE.cites.stroke),
        coupled: cssVar(canvas, EDGE_STYLE.coupled.stroke),
        cocited: cssVar(canvas, EDGE_STYLE.cocited.stroke),
      },
    };

    const draw = () => {
      const { width, height, dpr } = sizeRef.current;
      const scale = Math.min(width / WIDTH, height / HEIGHT);
      const offsetX = (width - WIDTH * scale) / 2;
      const offsetY = (height - HEIGHT * scale) / 2;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.setTransform(
        dpr * scale,
        0,
        0,
        dpr * scale,
        dpr * offsetX,
        dpr * offsetY,
      );

      for (const link of simLinks) {
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        if (source.x == null || source.y == null) continue;
        if (target.x == null || target.y == null) continue;
        const style = EDGE_STYLE[link.type];
        ctx.globalAlpha = style.opacity;
        ctx.strokeStyle = colors.edge[link.type];
        ctx.lineWidth = Math.min(4, 1 + Math.log2(link.weight + 1));
        ctx.setLineDash(style.dash);
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;

      for (const node of simNodes) {
        if (node.x == null || node.y == null) continue;
        const selected = node.id === selectedRef.current;
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius(node) + (selected ? 4 : 0), 0, Math.PI * 2);
        ctx.fillStyle = colors[node.kind];
        ctx.globalAlpha = selected ? 1 : 0.85;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.lineWidth = selected ? 2.5 : 1.5;
        ctx.strokeStyle = selected ? colors.ink : colors.nodeStroke;
        ctx.stroke();

        if (node.kind === "seed") {
          const label =
            node.label.length > 46 ? `${node.label.slice(0, 46)}…` : node.label;
          ctx.font = "11px system-ui, sans-serif";
          ctx.textAlign = "center";
          ctx.fillStyle = colors.ink;
          ctx.fillText(label, node.x, node.y - radius(node) - 8);
        }
      }
    };

    drawRef.current = draw;

    const simulation = forceSimulation<SimNode>(simNodes)
      .force(
        "link",
        forceLink<SimNode, SimLink>(simLinks)
          .id((node) => node.id)
          .distance((link) => (link.type === "cites" ? 90 : 55))
          .strength((link) => (link.type === "cites" ? 0.35 : 0.15)),
      )
      .force("charge", forceManyBody().strength(-190))
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide<SimNode>().radius((node) => radius(node) + 6))
      .on("tick", draw);

    draw();

    return () => {
      simulation.stop();
    };
  }, [nodes, edges]);

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const { width, height } = sizeRef.current;
    const scale = Math.min(width / WIDTH, height / HEIGHT);
    const offsetX = (width - WIDTH * scale) / 2;
    const offsetY = (height - HEIGHT * scale) / 2;
    const x = (event.clientX - rect.left - offsetX) / scale;
    const y = (event.clientY - rect.top - offsetY) / scale;

    let hit: SimNode | null = null;
    let best = Infinity;
    for (const node of nodesRef.current) {
      if (node.x == null || node.y == null) continue;
      const distance = Math.hypot(node.x - x, node.y - y);
      if (distance <= radius(node) + 6 && distance < best) {
        best = distance;
        hit = node;
      }
    }
    if (hit) onSelect(hit.id);
  };

  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-800 bg-slate-950/60">
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        role="img"
        aria-label={`Citation network with ${nodes.length} nodes and ${edges.length} edges`}
        className="block h-[560px] w-full cursor-pointer"
      />

      <ul className="sr-only">
        {nodes.map((node) => (
          <li key={node.id}>
            <button
              type="button"
              onClick={() => onSelect(node.id)}
              aria-pressed={node.id === selectedId}
              className="focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-10 focus:max-w-[calc(100%-1rem)] focus:rounded focus:border focus:border-slate-600 focus:bg-slate-900 focus:px-2 focus:py-1 focus:text-left focus:text-[11px] focus:text-slate-100 touch-target"
            >
              {node.label} ({node.kind})
            </button>
          </li>
        ))}
      </ul>

      <div className="absolute bottom-3 left-3 flex flex-wrap gap-3 rounded-lg border border-slate-800 bg-slate-900/85 px-3 py-2 text-[11px] text-slate-300">
        {(["seed", "citation", "reference", "cocited"] as const).map((kind) => (
          <span key={kind} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: `var(${KIND_COLOR[kind]})` }}
            />
            {kind}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 bg-slate-500" />
          cites
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 border-t border-dashed border-amber-400" />
          coupled
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 border-t border-dotted border-violet-400" />
          cocited
        </span>
      </div>
    </div>
  );
}
