/**
 * VerificationBadge — displays a colored dot + score for verified tasks.
 */

interface VerificationBadgeProps {
  score: number
  badge: string
}

const BADGE_CONFIG: Record<string, { dot: string; label: string }> = {
  green: { dot: 'bg-green-500', label: 'Verified' },
  amber: { dot: 'bg-amber-500', label: 'Partial' },
  red:   { dot: 'bg-red-500',   label: 'Failed' },
}

export default function VerificationBadge({ score, badge }: VerificationBadgeProps) {
  const config = BADGE_CONFIG[badge] ?? BADGE_CONFIG.red

  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-300"
      title={`Verification score: ${score.toFixed(4)} (${config.label})`}
    >
      <span className={`h-2 w-2 rounded-full ${config.dot}`} />
      {score.toFixed(2)}
    </span>
  )
}
