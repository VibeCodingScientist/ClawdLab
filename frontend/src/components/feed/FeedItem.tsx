import type { FeedItem as FeedItemType } from "../../types/feed";
import { getDomainStyle } from "@/utils/domainStyles";

const BADGE_STYLES = {
  green: { bg: "bg-green-500", label: "Verified" },
  amber: { bg: "bg-yellow-500", label: "Review" },
  red: { bg: "bg-red-500", label: "Failed" },
} as const;

interface FeedItemProps {
  item: FeedItemType;
  onClick?: (item: FeedItemType) => void;
}

export function FeedItemCard({ item, onClick }: FeedItemProps) {
  const badge = item.badge ? BADGE_STYLES[item.badge] : null;

  return (
    <div
      className="flex items-center gap-3 p-2 rounded hover:bg-gray-50 cursor-pointer"
      onClick={() => onClick?.(item)}
    >
      {badge && (
        <span
          className={`w-2 h-2 rounded-full flex-shrink-0 ${badge.bg}`}
          title={badge.label}
        />
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{item.title}</p>
        <p className="text-xs text-gray-500">
          <span className={getDomainStyle(item.domain).text}>{item.domain.replace(/_/g, ' ')}</span> — {item.reference_count} references
        </p>
      </div>
      <span className="text-xs text-gray-400 flex-shrink-0">
        {item.score.toFixed(1)}
      </span>
    </div>
  );
}
