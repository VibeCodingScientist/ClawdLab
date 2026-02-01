"""Tests for LabspecGenerator (protocol layer)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lab_dict(slug: str = "quantum-ml-lab", name: str = "Quantum ML Lab") -> dict:
    """Create a realistic lab data dictionary."""
    return {
        "slug": slug,
        "name": name,
        "description": "Exploring quantum advantage in machine learning",
        "governance_type": "democratic",
        "visibility": "public",
        "karma_requirement": 25,
        "domains": ["mathematics", "ml_ai"],
        "created_by": str(uuid4()),
    }


def _make_role_card(archetype: str = "theorist", filled: bool = False) -> dict:
    """Create a role card dictionary."""
    return {
        "id": str(uuid4()),
        "archetype": archetype,
        "pipeline_layer": "ideation",
        "min_karma": 10,
        "max_holders": 5,
    }


def _make_research_items(count: int = 3) -> dict:
    """Create a research items response dictionary."""
    items = []
    for i in range(count):
        items.append({
            "id": str(uuid4()),
            "title": f"Research Item {i + 1}",
            "domain": "mathematics",
            "status": "proposed",
            "proposed_by": str(uuid4()),
        })
    return {"items": items, "total": count}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _patch_lab_service():
    """Patch LabService used by LabspecGenerator."""
    with patch("platform.api.protocol.labspec_generator.LabService") as mock_cls:
        service = AsyncMock()

        lab = _make_lab_dict()
        service.get_lab = AsyncMock(return_value=lab)

        open_role = _make_role_card("experimentalist")
        service.get_unfilled_roles = AsyncMock(return_value=[open_role])

        all_roles = [_make_role_card("theorist"), open_role]
        service.list_role_cards = AsyncMock(return_value=all_roles)

        service.list_research_items = AsyncMock(return_value=_make_research_items(3))
        service.get_lab_stats = AsyncMock(return_value={
            "member_count": 8,
            "research_item_count": 3,
        })
        service.get_roundtable = AsyncMock(return_value={"entries": []})

        mock_cls.return_value = service

        yield service


@pytest.fixture
def generator():
    """Return a LabspecGenerator instance."""
    from platform.api.protocol.labspec_generator import LabspecGenerator

    return LabspecGenerator()


@pytest.fixture
def mock_db():
    """Return a mock async database session."""
    session = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateLabspecMd:
    """Tests for LabspecGenerator.generate_labspec_md."""

    @pytest.mark.asyncio
    async def test_generates_markdown_with_lab_name(self, generator, mock_db, _patch_lab_service):
        """Output must include the lab name as a heading."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        assert "# Quantum ML Lab" in content

    @pytest.mark.asyncio
    async def test_includes_yaml_frontmatter(self, generator, mock_db, _patch_lab_service):
        """Output must start with YAML frontmatter delimited by ---."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        assert content.startswith("---\n")
        # Frontmatter ends with a second ---
        lines = content.split("\n")
        # Find second occurrence of ---
        dash_indices = [i for i, line in enumerate(lines) if line.strip() == "---"]
        assert len(dash_indices) >= 2, "YAML frontmatter must have opening and closing ---"

    @pytest.mark.asyncio
    async def test_frontmatter_contains_slug(self, generator, mock_db, _patch_lab_service):
        """YAML frontmatter must include the lab slug."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        # Extract frontmatter (between first and second ---)
        parts = content.split("---")
        frontmatter = parts[1] if len(parts) >= 3 else ""
        assert "slug: quantum-ml-lab" in frontmatter

    @pytest.mark.asyncio
    async def test_frontmatter_contains_domains(self, generator, mock_db, _patch_lab_service):
        """YAML frontmatter must include the lab domains."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        parts = content.split("---")
        frontmatter = parts[1] if len(parts) >= 3 else ""
        assert "mathematics" in frontmatter
        assert "ml_ai" in frontmatter

    @pytest.mark.asyncio
    async def test_includes_open_roles_section(self, generator, mock_db, _patch_lab_service):
        """Output must include a Role Cards section with open positions."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        assert "## Role Cards" in content
        assert "OPEN" in content
        assert "open position(s)" in content.lower()

    @pytest.mark.asyncio
    async def test_includes_join_instructions(self, generator, mock_db, _patch_lab_service):
        """Output must include a How to Join section."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        assert "## How to Join" in content
        assert "quantum-ml-lab/join" in content

    @pytest.mark.asyncio
    async def test_includes_research_items(self, generator, mock_db, _patch_lab_service):
        """Output must include the Active Research section."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        assert "## Active Research" in content
        assert "Research Item 1" in content

    @pytest.mark.asyncio
    async def test_includes_research_focus(self, generator, mock_db, _patch_lab_service):
        """Output must include the Research Focus section."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        assert "## Research Focus" in content

    @pytest.mark.asyncio
    async def test_includes_karma_requirement_note(self, generator, mock_db, _patch_lab_service):
        """Join section should note the karma requirement when non-zero."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        assert "25" in content
        assert "karma" in content.lower()

    @pytest.mark.asyncio
    async def test_includes_generated_timestamp(self, generator, mock_db, _patch_lab_service):
        """Output must include a generation timestamp at the bottom."""
        content = await generator.generate_labspec_md(mock_db, "quantum-ml-lab")

        assert "*Generated:" in content
