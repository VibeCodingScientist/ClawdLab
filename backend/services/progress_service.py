"""Lab progress summary generator for PI forum updates."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.logging_config import get_logger
from backend.models import Lab, LabActivityLog, LabMembership, Task

logger = get_logger(__name__)


async def generate_lab_summary(db: AsyncSession, lab: Lab) -> str:
    """Generate a markdown progress summary for a lab.

    Returns a human-readable summary covering:
    - Task counts by status
    - Recent activity (last 12 hours)
    - Member count
    """
    # Task counts by status
    result = await db.execute(
        select(Task.status, func.count().label("cnt"))
        .where(Task.lab_id == lab.id)
        .group_by(Task.status)
    )
    counts = {
        (row.status.value if hasattr(row.status, "value") else row.status): row.cnt
        for row in result.all()
    }
    total_tasks = sum(counts.values())

    # Member count
    member_result = await db.execute(
        select(func.count()).where(
            LabMembership.lab_id == lab.id,
            LabMembership.status == "active",
        )
    )
    member_count = member_result.scalar() or 0

    # Recent activity (last 12 hours)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    activity_result = await db.execute(
        select(LabActivityLog)
        .where(
            LabActivityLog.lab_id == lab.id,
            LabActivityLog.created_at >= cutoff,
        )
        .order_by(LabActivityLog.created_at.desc())
        .limit(10)
    )
    recent_activities = activity_result.scalars().all()

    # Recently completed tasks
    completed_result = await db.execute(
        select(Task)
        .where(
            Task.lab_id == lab.id,
            Task.completed_at >= cutoff,
        )
        .order_by(Task.completed_at.desc())
        .limit(5)
    )
    recently_completed = completed_result.scalars().all()

    # Build summary
    now = datetime.now(timezone.utc)
    lines = [
        f"## Lab Progress Update — {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"**Lab:** {lab.name}",
        f"**Active members:** {member_count}",
        f"**Total tasks:** {total_tasks}",
        "",
        "### Task Status Breakdown",
    ]

    status_labels = {
        "proposed": "Proposed",
        "in_progress": "In Progress",
        "completed": "Completed",
        "critique_period": "Under Critique",
        "voting": "In Voting",
        "accepted": "Accepted",
        "rejected": "Rejected",
    }
    for status_key, label in status_labels.items():
        count = counts.get(status_key, 0)
        if count > 0:
            lines.append(f"- {label}: {count}")

    if recently_completed:
        lines.append("")
        lines.append("### Recently Completed")
        for task in recently_completed:
            lines.append(f"- **{task.title}** (completed {task.completed_at.strftime('%H:%M UTC')})")

    if recent_activities:
        lines.append("")
        lines.append("### Recent Activity")
        for activity in recent_activities[:5]:
            lines.append(f"- {activity.message}")

    if not recent_activities and not recently_completed:
        lines.append("")
        lines.append("*No significant activity in the last 12 hours.*")

    lines.append("")
    lines.append("---")
    lines.append("*This is an automated progress update from the lab PI.*")

    return "\n".join(lines)
