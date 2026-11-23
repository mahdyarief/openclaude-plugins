import { Chip } from "../ui";
import type { SearchScoping } from "../../lib/types";

export function QueryScopingPanel({
  scoping,
}: {
  scoping?: Record<string, SearchScoping>;
}) {
  if (Object.keys(scoping || {}).length === 0) return null;

  return (
            <div className="space-y-1 rounded border border-slate-800 bg-slate-900/40 p-2 text-[11px] text-slate-400">
              <div className="font-medium uppercase tracking-wide">
                Query scoping
              </div>
              {Object.entries(scoping || {}).map(([provider, scoping]) => (
                <div key={provider} className="flex flex-wrap items-center gap-1.5">
                  <span className="text-slate-300">{provider}:</span>
                  {scoping.honored.map((field) => (
                    <Chip key={`${provider}-h-${field}`}>{field}</Chip>
                  ))}
                  {scoping.degraded.length > 0 && (
                    <span className="text-amber-300/90">
                      {scoping.degraded.join(", ")} → free text
                    </span>
                  )}
                  {scoping.honored.length === 0 && scoping.degraded.length === 0 && (
                    <span className="text-slate-500">no clauses</span>
                  )}
                </div>
              ))}
            </div>
  );
}
