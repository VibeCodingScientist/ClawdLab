/**
 * LabWorkspacePage -- Route wrapper that extracts the lab slug from the URL and renders LabWorkspace.
 * Depends on: react-router-dom, LabWorkspace
 */
import { useParams } from "react-router-dom";
import { LabWorkspace } from "@/workspace/LabWorkspace";

export function LabWorkspacePage() {
  const { slug } = useParams<{ slug: string }>();

  if (!slug) {
    return <p className="p-4 text-gray-500">No lab specified.</p>;
  }

  return (
    <div className="max-w-[1024px] mx-auto">
      <LabWorkspace slug={slug} />
    </div>
  );
}
