import type { SearchResponse } from "./types";

export function paperKey(
  paper: SearchResponse["results"][number],
  index: number,
): string {
  return `${paper.doi ?? paper.title}-${index}`;
}
