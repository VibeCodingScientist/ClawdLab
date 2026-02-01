import type { WorkspaceAgent } from "../../types/workspace";

interface WorkspaceOverlayProps {
  selectedAgent: WorkspaceAgent | null;
  onClose: () => void;
}

export function WorkspaceOverlay({
  selectedAgent,
  onClose,
}: WorkspaceOverlayProps) {
  if (!selectedAgent) return null;

  return (
    <div className="absolute top-4 right-4 bg-white shadow-lg rounded-lg p-4 w-72 border">
      <div className="flex justify-between items-start">
        <h3 className="font-semibold text-sm">Agent Details</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-xs"
        >
          Close
        </button>
      </div>
      <dl className="mt-2 space-y-1 text-sm">
        <div className="flex justify-between">
          <dt className="text-gray-500">ID</dt>
          <dd className="font-mono text-xs">
            {selectedAgent.agent_id.slice(0, 12)}...
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Zone</dt>
          <dd>{selectedAgent.zone}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Status</dt>
          <dd>{selectedAgent.status}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Last Active</dt>
          <dd className="text-xs">
            {selectedAgent.last_action_at
              ? new Date(selectedAgent.last_action_at).toLocaleTimeString()
              : "N/A"}
          </dd>
        </div>
      </dl>
    </div>
  );
}
