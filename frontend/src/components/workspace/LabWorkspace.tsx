import { useEffect, useState } from "react";
import { useWorkspaceSSE } from "../../hooks/useWorkspaceSSE";
import { getWorkspaceState } from "../../api/workspace";
import type { WorkspaceAgent, WorkspaceZone } from "../../types/workspace";

const ZONE_LABELS: Record<WorkspaceZone, string> = {
  ideation: "Ideation Corner",
  library: "Library",
  bench: "Lab Bench",
  roundtable: "Roundtable",
  whiteboard: "Whiteboard",
  presentation: "Presentation Hall",
};

const ZONE_COLORS: Record<WorkspaceZone, string> = {
  ideation: "bg-yellow-50 border-yellow-300",
  library: "bg-blue-50 border-blue-300",
  bench: "bg-green-50 border-green-300",
  roundtable: "bg-purple-50 border-purple-300",
  whiteboard: "bg-orange-50 border-orange-300",
  presentation: "bg-red-50 border-red-300",
};

interface LabWorkspaceProps {
  slug: string;
}

export function LabWorkspace({ slug }: LabWorkspaceProps) {
  const { agents: liveAgents, connected } = useWorkspaceSSE(slug);
  const [agents, setAgents] = useState<WorkspaceAgent[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Load initial state
  useEffect(() => {
    getWorkspaceState(slug)
      .then((state) => setAgents(state.agents))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Failed to load workspace state";
        setError(message);
      });
  }, [slug]);

  // Merge live updates
  useEffect(() => {
    if (liveAgents.length > 0) {
      setAgents(liveAgents);
    }
  }, [liveAgents]);

  const zones: WorkspaceZone[] = [
    "ideation",
    "library",
    "bench",
    "roundtable",
    "whiteboard",
    "presentation",
  ];

  const agentsByZone = (zone: WorkspaceZone) =>
    agents.filter((a) => a.zone === zone);

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Lab Workspace: {slug}</h2>
        <span
          className={`px-2 py-1 rounded text-xs font-medium ${
            connected
              ? "bg-green-100 text-green-800"
              : "bg-gray-100 text-gray-500"
          }`}
        >
          {connected ? "Live" : "Connecting..."}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {zones.map((zone) => (
          <div
            key={zone}
            className={`border-2 rounded-lg p-4 min-h-[200px] ${ZONE_COLORS[zone]}`}
          >
            <h3 className="font-semibold text-sm mb-2">{ZONE_LABELS[zone]}</h3>
            <div className="space-y-1">
              {agentsByZone(zone).map((agent) => (
                <div
                  key={agent.agent_id}
                  className="flex items-center gap-2 bg-white rounded px-2 py-1 text-xs shadow-sm"
                >
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="font-mono truncate">
                    {agent.agent_id.slice(0, 8)}
                  </span>
                  <span className="text-gray-500 ml-auto">{agent.status}</span>
                </div>
              ))}
              {agentsByZone(zone).length === 0 && (
                <p className="text-xs text-gray-400 italic">Empty</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
