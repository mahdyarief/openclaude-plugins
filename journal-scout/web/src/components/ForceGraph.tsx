import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
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

type Viewport = { x: number; y: number; k: number };

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

const EDGE_TYPES: GraphEdge["type"][] = ["cites", "coupled", "cocited"];

function cssVar(canvas: HTMLCanvasElement, name: string): string {
  const value = getComputedStyle(canvas).getPropertyValue(name).trim();
  return value || "#888";
}

function radius(node: GraphNode): number {
  if (node.kind === "seed") return 13;
  const citations = node.citation_count ?? 0;
  return Math.min(11, 5 + Math.sqrt(citations) * 0.5);
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export function ForceGraph({
  nodes,
  edges,
  selectedId,
  onSelect,
  timeline = false,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  timeline?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const drawRef = useRef<() => void>(() => {});
  const selectedRef = useRef<string | null>(selectedId);
  const viewportRef = useRef<Viewport>({ x: 0, y: 0, k: 1 });
  const hoverRef = useRef<string | null>(null);
  const dragRef = useRef<{
    mode: "node" | "pan";
    node?: SimNode;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);
  const sizeRef = useRef({ width: WIDTH, height: HEIGHT, dpr: 1 });
  const timelineRef = useRef(timeline);
  const enabledRef = useRef<Record<GraphEdge["type"], boolean>>({
    cites: true,
    coupled: true,
    cocited: true,
  });
  const yearRangeRef = useRef<[number, number] | null>(null);

  const [enabled, setEnabled] = useState<Record<GraphEdge["type"], boolean>>({
    cites: true,
    coupled: true,
    cocited: true,
  });
  const [yearRange, setYearRange] = useState<[number, number] | null>(null);

  const years = useMemo(
    () => nodes.map((node) => node.year).filter((year): year is number => year != null),
    [nodes],
  );
  const minYear = years.length ? Math.min(...years) : null;
  const maxYear = years.length ? Math.max(...years) : null;

  useEffect(() => {
    enabledRef.current = enabled;
    drawRef.current();
  }, [enabled]);

  useEffect(() => {
    yearRangeRef.current = yearRange;
    drawRef.current();
  }, [yearRange]);

  useEffect(() => {
    timelineRef.current = timeline;
    drawRef.current();
  }, [timeline]);

  useEffect(() => {
    setYearRange(null);
    viewportRef.current = { x: 0, y: 0, k: 1 };
  }, [nodes]);

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

    const neighbors = new Map<string, Set<string>>();
    for (const link of simLinks) {
      const source = link.source as unknown as string;
      const target = link.target as unknown as string;
      if (!neighbors.has(source)) neighbors.set(source, new Set());
      if (!neighbors.has(target)) neighbors.set(target, new Set());
      neighbors.get(source)!.add(target);
      neighbors.get(target)!.add(source);
    }

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
      const viewport = viewportRef.current;
      const scale = Math.min(width / WIDTH, height / HEIGHT);
      const offsetX = (width - WIDTH * scale) / 2;
      const offsetY = (height - HEIGHT * scale) / 2;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.setTransform(
        dpr * scale * viewport.k,
        0,
        0,
        dpr * scale * viewport.k,
        dpr * (offsetX + viewport.x * scale),
        dpr * (offsetY + viewport.y * scale),
      );

      const selected = selectedRef.current;
      const hovered = hoverRef.current;
      const focus = hovered ?? selected;
      const focusedNeighbors = focus ? neighbors.get(focus) ?? new Set() : null;
      const range = yearRangeRef.current;
      const isVisible = (node: SimNode) => {
        if (!range) return true;
        if (node.year == null) return true;
        return node.year >= range[0] && node.year <= range[1];
      };

      for (const link of simLinks) {
        if (!enabledRef.current[link.type]) continue;
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        if (source.x == null || source.y == null) continue;
        if (target.x == null || target.y == null) continue;
        if (!isVisible(source) || !isVisible(target)) continue;
        const dim =
          focus != null &&
          source.id !== focus &&
          target.id !== focus;
        const style = EDGE_STYLE[link.type];
        ctx.globalAlpha = dim ? style.opacity * 0.12 : style.opacity;
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
        if (!isVisible(node)) continue;
        const isSelected = node.id === selected;
        const isHovered = node.id === hovered;
        const inFocus =
          focus == null || node.id === focus || (focusedNeighbors?.has(node.id) ?? false);
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius(node) + (isSelected ? 4 : 0), 0, Math.PI * 2);
        ctx.fillStyle = colors[node.kind];
        ctx.globalAlpha = inFocus ? (isSelected ? 1 : 0.9) : 0.18;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.lineWidth = isSelected || isHovered ? 2.5 : 1.5;
        ctx.strokeStyle = isSelected ? colors.ink : colors.nodeStroke;
        ctx.stroke();

        const showLabel =
          node.kind === "seed" || isSelected || isHovered || (focus != null && inFocus);
        if (showLabel) {
          ctx.font = `${isSelected || isHovered ? 12 : 11}px system-ui, sans-serif`;
          ctx.textAlign = "center";
          ctx.fillStyle = colors.ink;
          ctx.globalAlpha = inFocus ? 1 : 0.3;
          ctx.fillText(
            truncate(node.label, isSelected || isHovered ? 52 : 34),
            node.x,
            node.y - radius(node) - 8,
          );
          ctx.globalAlpha = 1;
        }
      }
    };

    drawRef.current = draw;

    const linkForce = forceLink<SimNode, SimLink>(simLinks)
      .id((node) => node.id)
      .distance((link) => (link.type === "cites" ? 90 : 55))
      .strength((link) => (link.type === "cites" ? 0.35 : 0.15));

    const simulation = forceSimulation<SimNode>(simNodes)
      .force("link", linkForce)
      .force("charge", forceManyBody().strength(-190))
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide<SimNode>().radius((node) => radius(node) + 6))
      .on("tick", draw);

    if (timelineRef.current) {
      // Timeline mode replaces the centering force with year-anchored X, so
      // the horizontal axis reads as publication year rather than a blob.
      const dated = simNodes.filter((node) => node.year != null);
      const low = dated.length ? Math.min(...dated.map((n) => n.year as number)) : 0;
      const high = dated.length ? Math.max(...dated.map((n) => n.year as number)) : 1;
      const span = Math.max(1, high - low);
      simulation
        .force("center", null)
        .force("x", forceX<SimNode>((node) => {
          if (node.year == null) return WIDTH / 2;
          return 60 + ((node.year - low) / span) * (WIDTH - 120);
        }).strength(0.9))
        .force("y", forceY<SimNode>(HEIGHT / 2).strength(0.06))
        .alpha(1)
        .restart();
    }

    draw();

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, timeline]);

  const toGraphSpace = (event: { clientX: number; clientY: number }) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const { width, height } = sizeRef.current;
    const scale = Math.min(width / WIDTH, height / HEIGHT);
    const offsetX = (width - WIDTH * scale) / 2;
    const offsetY = (height - HEIGHT * scale) / 2;
    const viewport = viewportRef.current;
    return {
      x: (event.clientX - rect.left - offsetX) / (scale * viewport.k) - viewport.x / viewport.k,
      y: (event.clientY - rect.top - offsetY) / (scale * viewport.k) - viewport.y / viewport.k,
    };
  };

  const hitTest = (event: { clientX: number; clientY: number }): SimNode | null => {
    const { x, y } = toGraphSpace(event);
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
    return hit;
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const node = hitTest(event);
    if (node) {
      dragRef.current = {
        mode: "node",
        node,
        startX: event.clientX,
        startY: event.clientY,
        originX: node.x ?? 0,
        originY: node.y ?? 0,
      };
      onSelect(node.id);
      return;
    }
    dragRef.current = {
      mode: "pan",
      startX: event.clientX,
      startY: event.clientY,
      originX: viewportRef.current.x,
      originY: viewportRef.current.y,
    };
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (drag?.mode === "node" && drag.node) {
      const { width, height } = sizeRef.current;
      const scale = Math.min(width / WIDTH, height / HEIGHT) * viewportRef.current.k;
      drag.node.fx = drag.originX + (event.clientX - drag.startX) / scale;
      drag.node.fy = drag.originY + (event.clientY - drag.startY) / scale;
      drawRef.current();
      return;
    }
    if (drag?.mode === "pan") {
      viewportRef.current = {
        ...viewportRef.current,
        x: drag.originX + (event.clientX - drag.startX),
        y: drag.originY + (event.clientY - drag.startY),
      };
      drawRef.current();
      return;
    }
    const hit = hitTest(event);
    const nextId = hit?.id ?? null;
    if (nextId !== hoverRef.current) {
      hoverRef.current = nextId;
      drawRef.current();
    }
  };

  const handlePointerUp = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    if (drag?.mode === "node" && drag.node) {
      drag.node.fx = null;
      drag.node.fy = null;
    }
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleWheel = (event: ReactWheelEvent<HTMLCanvasElement>) => {
    event.preventDefault();
    const viewport = viewportRef.current;
    const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
    viewportRef.current = {
      ...viewport,
      k: Math.min(4, Math.max(0.25, viewport.k * factor)),
    };
    drawRef.current();
  };

  const resetView = () => {
    viewportRef.current = { x: 0, y: 0, k: 1 };
    for (const node of nodesRef.current) {
      node.fx = null;
      node.fy = null;
    }
    drawRef.current();
  };

  const zoomBy = (factor: number) => {
    const viewport = viewportRef.current;
    viewportRef.current = {
      ...viewport,
      k: Math.min(4, Math.max(0.25, viewport.k * factor)),
    };
    drawRef.current();
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
        <span className="font-medium text-slate-400">Edges</span>
        {EDGE_TYPES.map((type) => (
          <label key={type} className="flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={enabled[type]}
              onChange={(event) =>
                setEnabled((prev) => ({ ...prev, [type]: event.target.checked }))
              }
              className="accent-sky-500"
            />
            <span className="capitalize">{type}</span>
          </label>
        ))}

        {minYear != null && maxYear != null && minYear !== maxYear ? (
          <span className="ml-auto flex items-center gap-2">
            <span className="text-slate-400">Year</span>
            <input
              type="range"
              min={minYear}
              max={maxYear}
              value={yearRange ? yearRange[0] : minYear}
              onChange={(event) =>
                setYearRange([Number(event.target.value), yearRange?.[1] ?? maxYear])
              }
              className="w-24 accent-sky-500"
            />
            <input
              type="range"
              min={minYear}
              max={maxYear}
              value={yearRange ? yearRange[1] : maxYear}
              onChange={(event) =>
                setYearRange([yearRange?.[0] ?? minYear, Number(event.target.value)])
              }
              className="w-24 accent-sky-500"
            />
            <span className="tabular-nums text-slate-400">
              {yearRange ? `${yearRange[0]}–${yearRange[1]}` : `${minYear}–${maxYear}`}
            </span>
          </span>
        ) : null}

        <span className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => zoomBy(1.2)}
            className="rounded border border-slate-700 px-2 py-0.5 hover:bg-slate-800"
            aria-label="Zoom in"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => zoomBy(1 / 1.2)}
            className="rounded border border-slate-700 px-2 py-0.5 hover:bg-slate-800"
            aria-label="Zoom out"
          >
            −
          </button>
          <button
            type="button"
            onClick={resetView}
            className="rounded border border-slate-700 px-2 py-0.5 hover:bg-slate-800"
          >
            Reset
          </button>
        </span>
      </div>

      <div className="relative overflow-hidden rounded-lg border border-slate-800 bg-slate-950/60">
        <canvas
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={() => {
            hoverRef.current = null;
            drawRef.current();
          }}
          onWheel={handleWheel}
          role="img"
          aria-label={`Citation network with ${nodes.length} nodes and ${edges.length} edges`}
          className="block h-[520px] w-full cursor-grab touch-none active:cursor-grabbing"
        />
      </div>
    </div>
  );
}


