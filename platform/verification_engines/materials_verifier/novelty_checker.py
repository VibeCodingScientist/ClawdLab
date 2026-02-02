"""Materials novelty checking across databases."""

import asyncio
from typing import Any

import aiohttp

from platform.verification_engines.materials_verifier.base import (
    BaseMaterialsVerifier,
    CrystalStructure,
    MaterialsNoveltyResult,
    MCPToolProvider,
    SimilarMaterial,
)
from platform.verification_engines.materials_verifier.config import get_settings
from platform.verification_engines.materials_verifier.materials_project import (
    MaterialsProjectClient,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AFLOWClient:
    """Client for AFLOW database API."""

    def __init__(self):
        """Initialize AFLOW client."""
        self._base_url = settings.aflow_api_endpoint

    async def search_by_formula(
        self,
        formula: str,
        max_results: int = 10,
    ) -> list[SimilarMaterial]:
        """Search AFLOW by chemical formula."""
        async with aiohttp.ClientSession() as session:
            try:
                # AFLOW query format
                query = f"?compound({formula}),paging(0,{max_results})"
                url = f"{self._base_url}{query}"

                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    materials = []

                    for entry in data if isinstance(data, list) else []:
                        auid = entry.get("auid", "")
                        materials.append(SimilarMaterial(
                            material_id=auid,
                            formula=entry.get("compound", ""),
                            source_database="aflow",
                            space_group=entry.get("spacegroup_relax"),
                            energy_above_hull=entry.get("enthalpy_formation_atom"),
                            url=f"http://aflowlib.org/material.php?id={auid}",
                        ))

                    return materials

            except Exception as e:
                logger.warning("aflow_search_error", formula=formula, error=str(e))
                return []

    async def search_by_elements(
        self,
        elements: list[str],
        max_results: int = 10,
    ) -> list[SimilarMaterial]:
        """Search AFLOW by chemical elements."""
        async with aiohttp.ClientSession() as session:
            try:
                species = ",".join(elements)
                query = f"?species({species}),paging(0,{max_results})"
                url = f"{self._base_url}{query}"

                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    materials = []

                    for entry in data if isinstance(data, list) else []:
                        auid = entry.get("auid", "")
                        materials.append(SimilarMaterial(
                            material_id=auid,
                            formula=entry.get("compound", ""),
                            source_database="aflow",
                            space_group=entry.get("spacegroup_relax"),
                            energy_above_hull=entry.get("enthalpy_formation_atom"),
                            url=f"http://aflowlib.org/material.php?id={auid}",
                        ))

                    return materials

            except Exception as e:
                logger.warning("aflow_search_error", elements=elements, error=str(e))
                return []


class OQMDClient:
    """Client for Open Quantum Materials Database (OQMD) API."""

    def __init__(self):
        """Initialize OQMD client."""
        self._base_url = settings.oqmd_api_endpoint

    async def search_by_formula(
        self,
        formula: str,
        max_results: int = 10,
    ) -> list[SimilarMaterial]:
        """Search OQMD by chemical formula."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self._base_url}formationenergy"
                params = {
                    "composition": formula,
                    "limit": max_results,
                }

                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    materials = []

                    for entry in data.get("data", []):
                        entry_id = str(entry.get("entry_id", ""))
                        materials.append(SimilarMaterial(
                            material_id=f"oqmd-{entry_id}",
                            formula=entry.get("composition", ""),
                            source_database="oqmd",
                            space_group=entry.get("spacegroup"),
                            energy_above_hull=entry.get("delta_e"),
                            url=f"http://oqmd.org/materials/entry/{entry_id}",
                        ))

                    return materials

            except Exception as e:
                logger.warning("oqmd_search_error", formula=formula, error=str(e))
                return []

    async def search_by_elements(
        self,
        elements: list[str],
        max_results: int = 10,
    ) -> list[SimilarMaterial]:
        """Search OQMD by chemical elements."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self._base_url}formationenergy"
                params = {
                    "element_set": ",".join(elements),
                    "limit": max_results,
                }

                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    materials = []

                    for entry in data.get("data", []):
                        entry_id = str(entry.get("entry_id", ""))
                        materials.append(SimilarMaterial(
                            material_id=f"oqmd-{entry_id}",
                            formula=entry.get("composition", ""),
                            source_database="oqmd",
                            space_group=entry.get("spacegroup"),
                            energy_above_hull=entry.get("delta_e"),
                            url=f"http://oqmd.org/materials/entry/{entry_id}",
                        ))

                    return materials

            except Exception as e:
                logger.warning("oqmd_search_error", elements=elements, error=str(e))
                return []


class MaterialsNoveltyChecker(BaseMaterialsVerifier):
    """
    Check novelty of materials across multiple databases.

    Searches:
    - Materials Project (MP)
    - AFLOW
    - OQMD
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize novelty checker."""
        super().__init__(tool_provider)
        self._mp_client = MaterialsProjectClient(tool_provider)
        self._aflow_client = AFLOWClient()
        self._oqmd_client = OQMDClient()

    @property
    def component_name(self) -> str:
        return "materials_novelty_checker"

    async def verify(
        self,
        structure: CrystalStructure,
    ) -> MaterialsNoveltyResult:
        """Check structure novelty."""
        return await self.check_novelty(structure)

    async def check_novelty(
        self,
        structure: CrystalStructure,
        check_databases: list[str] | None = None,
    ) -> MaterialsNoveltyResult:
        """
        Check if a material is novel by searching multiple databases.

        Args:
            structure: Crystal structure to check
            check_databases: Databases to check (default: all)

        Returns:
            MaterialsNoveltyResult with novelty assessment
        """
        check_databases = check_databases or ["mp", "aflow", "oqmd"]

        # Try MCP tool first
        if await self._has_tool("check_materials_novelty"):
            result = await self._invoke_tool(
                "check_materials_novelty",
                {
                    "composition": structure.composition,
                    "space_group": structure.space_group,
                    "cif_string": structure.cif_string,
                    "databases": check_databases,
                },
            )
            return self._parse_mcp_result(result)

        # Fall back to local database searches
        similar_materials = []

        # Search all databases in parallel
        tasks = []
        if "mp" in check_databases:
            tasks.append(self._search_mp(structure))
        if "aflow" in check_databases:
            tasks.append(self._search_aflow(structure))
        if "oqmd" in check_databases:
            tasks.append(self._search_oqmd(structure))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                similar_materials.extend(result)
            elif isinstance(result, Exception):
                logger.warning("novelty_search_error", error=str(result))

        # Analyze novelty
        return self._analyze_novelty(structure, similar_materials)

    async def _search_mp(self, structure: CrystalStructure) -> list[SimilarMaterial]:
        """Search Materials Project."""
        return await self._mp_client.find_similar_materials(
            composition=structure.composition,
            space_group=structure.space_group,
            max_results=10,
        )

    async def _search_aflow(self, structure: CrystalStructure) -> list[SimilarMaterial]:
        """Search AFLOW."""
        materials = await self._aflow_client.search_by_formula(
            formula=structure.composition,
            max_results=10,
        )

        # Calculate similarity
        for mat in materials:
            mat.structure_similarity = self._calculate_similarity(structure, mat)

        return materials

    async def _search_oqmd(self, structure: CrystalStructure) -> list[SimilarMaterial]:
        """Search OQMD."""
        materials = await self._oqmd_client.search_by_formula(
            formula=structure.composition,
            max_results=10,
        )

        # Calculate similarity
        for mat in materials:
            mat.structure_similarity = self._calculate_similarity(structure, mat)

        return materials

    def _calculate_similarity(
        self,
        structure: CrystalStructure,
        material: SimilarMaterial,
    ) -> float:
        """Calculate structure similarity score."""
        similarity = 1.0

        # Check composition match
        if structure.composition != material.formula:
            similarity *= 0.5

        # Check space group match
        if structure.space_group and material.space_group:
            if structure.space_group != material.space_group:
                similarity *= 0.7

        return similarity

    def _analyze_novelty(
        self,
        structure: CrystalStructure,
        similar_materials: list[SimilarMaterial],
    ) -> MaterialsNoveltyResult:
        """Analyze novelty based on search results."""
        if not similar_materials:
            # No similar materials found - novel
            return MaterialsNoveltyResult(
                is_novel=True,
                novelty_score=1.0,
                similar_materials=[],
                composition_novel=True,
                structure_novel=True,
                analysis="No similar materials found in MP, AFLOW, or OQMD databases.",
            )

        # Sort by similarity
        similar_materials.sort(
            key=lambda m: m.structure_similarity or 0,
            reverse=True,
        )

        closest_match = similar_materials[0] if similar_materials else None
        max_similarity = closest_match.structure_similarity if closest_match else 0

        # Check composition novelty
        composition_novel = not any(
            m.formula == structure.composition for m in similar_materials
        )

        # Check structure novelty (same composition AND space group)
        structure_novel = not any(
            m.formula == structure.composition and m.space_group == structure.space_group
            for m in similar_materials
        )

        # Calculate novelty score
        novelty_score = 1.0 - (max_similarity or 0)

        # Determine if novel
        is_novel = novelty_score >= settings.novelty_min_score

        # Build analysis
        analysis_parts = []
        if not composition_novel:
            analysis_parts.append(f"Composition {structure.composition} exists in databases.")
        if not structure_novel:
            analysis_parts.append(
                f"Structure with space group {structure.space_group} already known."
            )
        if is_novel:
            analysis_parts.append("Material considered novel based on structure differences.")
        else:
            analysis_parts.append("Material appears to be known or very similar to existing materials.")

        analysis = " ".join(analysis_parts)

        return MaterialsNoveltyResult(
            is_novel=is_novel,
            novelty_score=novelty_score,
            similar_materials=similar_materials[:10],  # Top 10
            closest_match=closest_match,
            composition_novel=composition_novel,
            structure_novel=structure_novel,
            analysis=analysis,
        )

    def _parse_mcp_result(self, result: dict[str, Any]) -> MaterialsNoveltyResult:
        """Parse MCP tool result into MaterialsNoveltyResult."""
        similar_materials = [
            SimilarMaterial(
                material_id=m.get("material_id", ""),
                formula=m.get("formula", ""),
                source_database=m.get("source", ""),
                space_group=m.get("space_group"),
                energy_above_hull=m.get("energy_above_hull"),
                structure_similarity=m.get("similarity"),
                url=m.get("url"),
            )
            for m in result.get("similar_materials", [])
        ]

        closest_data = result.get("closest_match")
        closest_match = (
            SimilarMaterial(
                material_id=closest_data.get("material_id", ""),
                formula=closest_data.get("formula", ""),
                source_database=closest_data.get("source", ""),
                space_group=closest_data.get("space_group"),
                energy_above_hull=closest_data.get("energy_above_hull"),
                structure_similarity=closest_data.get("similarity"),
                url=closest_data.get("url"),
            )
            if closest_data
            else None
        )

        return MaterialsNoveltyResult(
            is_novel=result.get("is_novel", False),
            novelty_score=result.get("novelty_score", 0.0),
            similar_materials=similar_materials,
            closest_match=closest_match,
            composition_novel=result.get("composition_novel", True),
            structure_novel=result.get("structure_novel", True),
            analysis=result.get("analysis", ""),
        )

    async def search_all_databases(
        self,
        composition: str,
        elements: list[str] | None = None,
    ) -> dict[str, list[SimilarMaterial]]:
        """
        Search all databases for materials.

        Args:
            composition: Chemical formula
            elements: List of elements (optional)

        Returns:
            Dict mapping database name to materials found
        """
        results = {"mp": [], "aflow": [], "oqmd": []}

        # Search by formula in parallel
        mp_task = self._mp_client.search_by_formula(composition)
        aflow_task = self._aflow_client.search_by_formula(composition)
        oqmd_task = self._oqmd_client.search_by_formula(composition)

        search_results = await asyncio.gather(
            mp_task, aflow_task, oqmd_task,
            return_exceptions=True,
        )

        # Convert MP results to SimilarMaterial
        if isinstance(search_results[0], list):
            for mat in search_results[0]:
                results["mp"].append(SimilarMaterial(
                    material_id=mat.material_id,
                    formula=mat.formula_pretty,
                    source_database="mp",
                    space_group=mat.space_group,
                    energy_above_hull=mat.energy_above_hull,
                    url=f"https://materialsproject.org/materials/{mat.material_id}",
                ))

        if isinstance(search_results[1], list):
            results["aflow"] = search_results[1]

        if isinstance(search_results[2], list):
            results["oqmd"] = search_results[2]

        return results
