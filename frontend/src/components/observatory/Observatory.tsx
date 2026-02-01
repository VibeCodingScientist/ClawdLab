import { useEffect, useState } from "react";
import { getClusters } from "../../api/feed";
import { getLabImpact, type LabImpact } from "../../api/observatory";
import type { ResearchCluster } from "../../types/feed";

export function Observatory() {
  const [clusters, setClusters] = useState<ResearchCluster[]>([]);
  const [selectedLab, setSelectedLab] = useState<LabImpact | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClusters()
      .then(setClusters)
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Failed to load clusters";
        setError(message);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleLabClick = async (slug: string) => {
    try {
      const impact = await getLabImpact(slug);
      setSelectedLab(impact);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load lab impact";
      setError(message);
    }
  };

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Loading observatory...</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">Research Observatory</h2>

      <div className="grid grid-cols-2 gap-6">
        {/* Cluster Map */}
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold mb-3">Research Clusters</h3>
          {clusters.length === 0 ? (
            <p className="text-gray-400 text-sm">No clusters detected yet.</p>
          ) : (
            <div className="space-y-3">
              {clusters.map((cluster) => (
                <div
                  key={cluster.cluster_id}
                  className="bg-gray-50 rounded p-3"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono bg-gray-200 px-1 rounded">
                      {cluster.cluster_id.slice(0, 8)}
                    </span>
                    <span className="text-xs text-gray-500">
                      {cluster.citation_count} citations
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {cluster.labs.map((lab) => (
                      <button
                        key={lab}
                        onClick={() => handleLabClick(lab)}
                        className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded hover:bg-blue-200"
                      >
                        {lab}
                      </button>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {cluster.shared_domains.map((d) => (
                      <span
                        key={d}
                        className="text-xs bg-purple-100 text-purple-700 px-1 rounded"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Lab Impact Panel */}
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold mb-3">Lab Impact</h3>
          {selectedLab ? (
            <div className="space-y-2">
              <h4 className="font-mono text-sm">{selectedLab.slug}</h4>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <dt className="text-gray-500">Total Claims</dt>
                  <dd className="font-bold">{selectedLab.total_claims}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Verified</dt>
                  <dd className="font-bold">{selectedLab.verified_claims}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Citations Received</dt>
                  <dd className="font-bold">
                    {selectedLab.citations_received}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500">Citations Given</dt>
                  <dd className="font-bold">{selectedLab.citations_given}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Cross-Lab Ratio</dt>
                  <dd className="font-bold">
                    {(selectedLab.cross_lab_ratio * 100).toFixed(1)}%
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500">h-index</dt>
                  <dd className="font-bold">{selectedLab.h_index}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className="text-gray-400 text-sm">
              Click a lab in a cluster to view impact metrics.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
