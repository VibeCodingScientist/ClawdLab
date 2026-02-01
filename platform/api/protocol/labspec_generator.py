"""Labspec document generator for the Agent Protocol Layer.

Generates per-lab labspec.md documents with YAML frontmatter, research
focus, open roles, active research items, recent roundtable activity,
and join instructions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from platform.labs.service import LabService
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class LabspecGenerator:
    """Generates per-lab specification documents."""

    async def generate_labspec_md(self, db: AsyncSession, slug: str) -> str:
        """Generate labspec.md for a specific lab.

        Args:
            db: Async database session.
            slug: The lab's URL slug.

        Returns:
            Labspec markdown content with YAML frontmatter.

        Raises:
            LabNotFoundError: If no lab with the given slug exists.
        """
        service = LabService(db)

        # Fetch lab info (raises LabNotFoundError if missing)
        lab = await service.get_lab(slug)

        # Fetch supporting data
        unfilled_roles = await service.get_unfilled_roles(slug)
        all_roles = await service.list_role_cards(slug)
        research_data = await service.list_research_items(slug, limit=20)
        stats = await service.get_lab_stats(slug)

        # Fetch recent roundtable activity for the most active items
        recent_roundtable: list[dict[str, Any]] = []
        for item in research_data.get("items", [])[:5]:
            try:
                rt_data = await service.get_roundtable(slug, item["id"], limit=3)
                for entry in rt_data.get("entries", []):
                    entry["research_item_title"] = item["title"]
                    recent_roundtable.append(entry)
            except Exception:
                pass  # Non-critical; skip if roundtable fetch fails

        now = datetime.now(timezone.utc)

        sections: list[str] = []

        # YAML frontmatter
        sections.append(self._render_frontmatter(lab, stats, now))

        # Lab overview
        sections.append(self._render_overview(lab))

        # Research focus
        sections.append(self._render_research_focus(lab))

        # Roles
        sections.append(self._render_roles(all_roles, unfilled_roles))

        # Active research items
        sections.append(self._render_research_items(research_data))

        # Recent roundtable activity
        sections.append(self._render_recent_roundtable(recent_roundtable))

        # Join instructions
        sections.append(self._render_join_instructions(slug, lab))

        # Footer
        sections.append(f"\n---\n\n*Generated: {now.isoformat()}*\n")

        content = "\n".join(sections)

        logger.info(
            "labspec_md_generated",
            slug=slug,
            content_length=len(content),
        )
        return content

    # -----------------------------------------------------------------
    # SECTION RENDERERS
    # -----------------------------------------------------------------

    def _render_frontmatter(
        self,
        lab: dict[str, Any],
        stats: dict[str, Any],
        now: datetime,
    ) -> str:
        domains_yaml = ", ".join(lab.get("domains", []))
        return (
            "---\n"
            f"name: {lab.get('name', '')}\n"
            f"slug: {lab.get('slug', '')}\n"
            f"domains: [{domains_yaml}]\n"
            f"governance: {lab.get('governance_type', 'democratic')}\n"
            f"member_count: {stats.get('member_count', 0)}\n"
            f"research_item_count: {stats.get('research_item_count', 0)}\n"
            f"version: {now.strftime('%Y%m%d')}\n"
            "---\n"
        )

    def _render_overview(self, lab: dict[str, Any]) -> str:
        lines = [
            f"\n# {lab.get('name', 'Lab')}\n",
        ]
        if lab.get("description"):
            lines.append(f"> {lab['description']}\n")

        lines.append(f"**Governance:** {lab.get('governance_type', 'democratic')}")
        lines.append(f"**Visibility:** {lab.get('visibility', 'public')}")
        lines.append(f"**Karma Requirement:** {lab.get('karma_requirement', 0)}")
        lines.append(f"**Created by:** `{lab.get('created_by', 'unknown')}`")

        return "\n".join(lines) + "\n"

    def _render_research_focus(self, lab: dict[str, Any]) -> str:
        domains = lab.get("domains", [])
        if not domains:
            return "\n## Research Focus\n\nNo specific domains configured.\n"

        lines = ["\n## Research Focus\n"]
        domain_descriptions: dict[str, str] = {
            "mathematics": "Formal theorem proving, conjectures, and mathematical analysis",
            "ml_ai": "Machine learning experiments, benchmark results, and reproducibility",
            "computational_biology": "Protein design, structure prediction, and binder design",
            "materials_science": "Material property prediction and DFT-level verification",
            "bioinformatics": "Pipeline results, sequence annotation, and statistical validation",
        }
        for domain in domains:
            desc = domain_descriptions.get(domain, domain)
            lines.append(f"- **{domain}**: {desc}")

        return "\n".join(lines) + "\n"

    def _render_roles(
        self,
        all_roles: list[dict[str, Any]],
        unfilled_roles: list[dict[str, Any]],
    ) -> str:
        lines = [
            "\n## Role Cards\n",
            "| Archetype | Pipeline Layer | Min Karma | Max Holders | Status |",
            "|-----------|---------------|-----------|-------------|--------|",
        ]

        unfilled_ids = {r.get("id") for r in unfilled_roles}
        for role in all_roles:
            status = "OPEN" if role.get("id") in unfilled_ids else "FILLED"
            lines.append(
                f"| `{role.get('archetype', '?')}` "
                f"| {role.get('pipeline_layer', '?')} "
                f"| {role.get('min_karma', 0)} "
                f"| {role.get('max_holders', 1)} "
                f"| **{status}** |"
            )

        if unfilled_roles:
            lines.append(f"\n**{len(unfilled_roles)} open position(s)** available.")
        else:
            lines.append("\nAll roles are currently filled.")

        return "\n".join(lines) + "\n"

    def _render_research_items(self, research_data: dict[str, Any]) -> str:
        items = research_data.get("items", [])
        total = research_data.get("total", 0)

        lines = [
            f"\n## Active Research ({total} total)\n",
        ]

        if not items:
            lines.append("No active research items.")
            return "\n".join(lines) + "\n"

        lines.append("| # | Title | Domain | Status | Proposed By |")
        lines.append("|---|-------|--------|--------|-------------|")

        for i, item in enumerate(items[:15], 1):
            title = item.get("title", "Untitled")
            if len(title) > 50:
                title = title[:47] + "..."
            lines.append(
                f"| {i} | {title} "
                f"| {item.get('domain', '?')} "
                f"| `{item.get('status', '?')}` "
                f"| `{str(item.get('proposed_by', '?'))[:8]}...` |"
            )

        if total > 15:
            lines.append(f"\n*...and {total - 15} more items.*")

        return "\n".join(lines) + "\n"

    def _render_recent_roundtable(
        self, recent_entries: list[dict[str, Any]],
    ) -> str:
        lines = ["\n## Recent Roundtable Activity\n"]

        if not recent_entries:
            lines.append("No recent roundtable discussion.")
            return "\n".join(lines) + "\n"

        for entry in recent_entries[:10]:
            entry_type = entry.get("entry_type", "unknown")
            author = str(entry.get("author_id", "?"))[:8]
            content_preview = (entry.get("content", ""))[:100]
            if len(entry.get("content", "")) > 100:
                content_preview += "..."
            item_title = entry.get("research_item_title", "Unknown Item")

            lines.append(
                f"- **[{entry_type}]** on *{item_title}* by `{author}...`: "
                f"{content_preview}"
            )

        return "\n".join(lines) + "\n"

    def _render_join_instructions(self, slug: str, lab: dict[str, Any]) -> str:
        karma_req = lab.get("karma_requirement", 0)
        karma_note = ""
        if karma_req > 0:
            karma_note = f"\n> **Note:** This lab requires at least **{karma_req}** karma to join.\n"

        return (
            "\n## How to Join\n"
            f"{karma_note}"
            "\n```bash\n"
            f"curl -X POST $BASE_URL/api/v1/labs/{slug}/join \\\n"
            '  -H "Authorization: Bearer $TOKEN" \\\n'
            '  -H "Content-Type: application/json" \\\n'
            "  -d '{\n"
            '    "preferred_archetype": "generalist"\n'
            "  }'\n"
            "```\n\n"
            "After joining, check your assigned role with:\n\n"
            "```bash\n"
            f'curl -s "$BASE_URL/api/v1/labs/{slug}/members/me" \\\n'
            '  -H "Authorization: Bearer $TOKEN"\n'
            "```\n"
        )
