/**
 * GlobalFeed -- Filterable global research feed component with badge indicators.
 * Depends on: feed API, FeedItem type
 */
import { useEffect, useState } from "react";
import { getFeed } from "@/api/feed";
import type { FeedItem } from "@/types/feed";
import { getErrorMessage } from "@/types";

const BADGE_COLORS = {
  green: "bg-green-100 text-green-800",
  amber: "bg-yellow-100 text-yellow-800",
  red: "bg-red-100 text-red-800",
} as const;

export function GlobalFeed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [domain, setDomain] = useState<string | undefined>();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getFeed({ domain, limit: 50 })
      .then((res) => {
        if (!cancelled) setItems(res.items);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(getErrorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [domain]);

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Global Research Feed</h2>
        <select
          aria-label="Filter by domain"
          value={domain || ""}
          onChange={(e) => setDomain(e.target.value || undefined)}
          className="text-sm border rounded px-2 py-1"
        >
          <option value="">All Domains</option>
          <option value="mathematics">Mathematics</option>
          <option value="ml_ai">ML/AI</option>
          <option value="computational_biology">Comp Bio</option>
          <option value="materials_science">Materials</option>
          <option value="bioinformatics">Bioinformatics</option>
        </select>
      </div>

      {error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
      ) : loading ? (
        <p className="text-gray-500">Loading feed...</p>
      ) : items.length === 0 ? (
        <p className="text-gray-400">No verified claims yet.</p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.id}
              className="border rounded-lg p-3 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="font-medium text-sm">{item.title}</h3>
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                    <span>{item.domain}</span>
                    {item.lab_slug && <span>Lab: {item.lab_slug}</span>}
                    <span>{item.citation_count} citations</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {item.badge && (
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        BADGE_COLORS[item.badge]
                      }`}
                    >
                      {item.badge.toUpperCase()}
                    </span>
                  )}
                  <span className="text-xs text-gray-400">
                    {item.score.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
