"""Materials Project API integration."""

from dataclasses import dataclass
from typing import Any

import aiohttp

from platform.verification_engines.materials_verifier.base import (
    CrystalStructure,
    LatticeParameters,
    AtomSite,
    CrystalSystem,
    MCPToolProvider,
    SimilarMaterial,
    StabilityClass,
    StabilityResult,
)
from platform.verification_engines.materials_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class MPMaterial:
    """Material entry from Materials Project."""

    material_id: str
    formula: str
    formula_pretty: str
    energy_per_atom: float
    energy_above_hull: float
    is_stable: bool
    space_group: str | None
    crystal_system: str | None
    band_gap: float | None
    nsites: int
    volume: float | None
    density: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "formula": self.formula,
            "formula_pretty": self.formula_pretty,
            "energy_per_atom": self.energy_per_atom,
            "energy_above_hull": self.energy_above_hull,
            "is_stable": self.is_stable,
            "space_group": self.space_group,
            "crystal_system": self.crystal_system,
            "band_gap": self.band_gap,
            "nsites": self.nsites,
            "volume": self.volume,
            "density": self.density,
        }


class MaterialsProjectClient:
    """Client for Materials Project API."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize Materials Project client."""
        self._api_key = settings.materials_project_api_key
        self._base_url = settings.materials_project_endpoint
        self._tool_provider = tool_provider

    async def get_material(self, material_id: str) -> MPMaterial | None:
        """Get material by MP ID."""
        # Check for MCP tool
        if self._tool_provider and await self._tool_provider.has_tool("mp_get_material"):
            result = await self._tool_provider.invoke_tool(
                tool_name="mp_get_material",
                parameters={"material_id": material_id},
            )
            if result:
                return MPMaterial(**result)

        # Use REST API
        if not self._api_key:
            logger.warning("Materials Project API key not configured")
            return None

        async with aiohttp.ClientSession() as session:
            try:
                headers = {"X-API-KEY": self._api_key}
                url = f"{self._base_url}/materials/summary/{material_id}"

                params = {
                    "fields": "material_id,formula_pretty,formula_anonymous,"
                              "energy_per_atom,energy_above_hull,is_stable,"
                              "symmetry,nsites,volume,density,band_gap",
                }

                async with session.get(url, headers=headers, params=params, timeout=30) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    mat = data.get("data", [{}])[0] if data.get("data") else {}

                    if not mat:
                        return None

                    symmetry = mat.get("symmetry", {})

                    return MPMaterial(
                        material_id=mat.get("material_id", ""),
                        formula=mat.get("formula_anonymous", ""),
                        formula_pretty=mat.get("formula_pretty", ""),
                        energy_per_atom=mat.get("energy_per_atom", 0.0),
                        energy_above_hull=mat.get("energy_above_hull", 0.0),
                        is_stable=mat.get("is_stable", False),
                        space_group=symmetry.get("symbol"),
                        crystal_system=symmetry.get("crystal_system"),
                        band_gap=mat.get("band_gap"),
                        nsites=mat.get("nsites", 0),
                        volume=mat.get("volume"),
                        density=mat.get("density"),
                    )

            except Exception as e:
                logger.warning("mp_fetch_error", material_id=material_id, error=str(e))
                return None

    async def get_structure(self, material_id: str) -> CrystalStructure | None:
        """Get crystal structure for a material."""
        if not self._api_key:
            return None

        async with aiohttp.ClientSession() as session:
            try:
                headers = {"X-API-KEY": self._api_key}
                url = f"{self._base_url}/materials/summary/{material_id}"

                params = {
                    "fields": "structure",
                }

                async with session.get(url, headers=headers, params=params, timeout=30) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    mat = data.get("data", [{}])[0] if data.get("data") else {}
                    structure_data = mat.get("structure")

                    if not structure_data:
                        return None

                    return self._parse_structure(structure_data, material_id)

            except Exception as e:
                logger.warning("mp_structure_error", material_id=material_id, error=str(e))
                return None

    def _parse_structure(self, data: dict[str, Any], source: str) -> CrystalStructure:
        """Parse MP structure data into CrystalStructure."""
        lattice = data.get("lattice", {})
        matrix = lattice.get("matrix", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])

        # Calculate lattice parameters from matrix
        import math

        def vec_length(v):
            return math.sqrt(sum(x * x for x in v))

        def vec_angle(v1, v2):
            dot = sum(a * b for a, b in zip(v1, v2))
            return math.degrees(math.acos(dot / (vec_length(v1) * vec_length(v2))))

        a = vec_length(matrix[0])
        b = vec_length(matrix[1])
        c = vec_length(matrix[2])
        alpha = vec_angle(matrix[1], matrix[2])
        beta = vec_angle(matrix[0], matrix[2])
        gamma = vec_angle(matrix[0], matrix[1])

        lattice_params = LatticeParameters(
            a=a, b=b, c=c,
            alpha=alpha, beta=beta, gamma=gamma,
            volume=lattice.get("volume"),
        )

        sites = []
        for site in data.get("sites", []):
            species = site.get("species", [{}])[0]
            coords = site.get("abc", [0, 0, 0])
            sites.append(AtomSite(
                species=species.get("element", "X"),
                x=coords[0],
                y=coords[1],
                z=coords[2],
                occupancy=species.get("occu", 1.0),
            ))

        return CrystalStructure(
            composition=data.get("composition", {}).get("reduced_formula", ""),
            lattice=lattice_params,
            sites=sites,
            source=f"mp:{source}",
        )

    async def search_by_formula(
        self,
        formula: str,
        max_results: int = 10,
    ) -> list[MPMaterial]:
        """Search Materials Project by formula."""
        if not self._api_key:
            return []

        async with aiohttp.ClientSession() as session:
            try:
                headers = {"X-API-KEY": self._api_key}
                url = f"{self._base_url}/materials/summary/"

                params = {
                    "formula": formula,
                    "fields": "material_id,formula_pretty,energy_per_atom,"
                              "energy_above_hull,is_stable,symmetry,nsites,band_gap",
                    "_limit": max_results,
                }

                async with session.get(url, headers=headers, params=params, timeout=30) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    materials = []

                    for mat in data.get("data", []):
                        symmetry = mat.get("symmetry", {})
                        materials.append(MPMaterial(
                            material_id=mat.get("material_id", ""),
                            formula=mat.get("formula_anonymous", ""),
                            formula_pretty=mat.get("formula_pretty", ""),
                            energy_per_atom=mat.get("energy_per_atom", 0.0),
                            energy_above_hull=mat.get("energy_above_hull", 0.0),
                            is_stable=mat.get("is_stable", False),
                            space_group=symmetry.get("symbol"),
                            crystal_system=symmetry.get("crystal_system"),
                            band_gap=mat.get("band_gap"),
                            nsites=mat.get("nsites", 0),
                            volume=None,
                            density=None,
                        ))

                    return materials

            except Exception as e:
                logger.warning("mp_search_error", formula=formula, error=str(e))
                return []

    async def search_by_elements(
        self,
        elements: list[str],
        max_results: int = 10,
    ) -> list[MPMaterial]:
        """Search Materials Project by chemical elements."""
        if not self._api_key:
            return []

        async with aiohttp.ClientSession() as session:
            try:
                headers = {"X-API-KEY": self._api_key}
                url = f"{self._base_url}/materials/summary/"

                params = {
                    "elements": ",".join(elements),
                    "fields": "material_id,formula_pretty,energy_per_atom,"
                              "energy_above_hull,is_stable,symmetry,nsites,band_gap",
                    "_limit": max_results,
                }

                async with session.get(url, headers=headers, params=params, timeout=30) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    materials = []

                    for mat in data.get("data", []):
                        symmetry = mat.get("symmetry", {})
                        materials.append(MPMaterial(
                            material_id=mat.get("material_id", ""),
                            formula=mat.get("formula_anonymous", ""),
                            formula_pretty=mat.get("formula_pretty", ""),
                            energy_per_atom=mat.get("energy_per_atom", 0.0),
                            energy_above_hull=mat.get("energy_above_hull", 0.0),
                            is_stable=mat.get("is_stable", False),
                            space_group=symmetry.get("symbol"),
                            crystal_system=symmetry.get("crystal_system"),
                            band_gap=mat.get("band_gap"),
                            nsites=mat.get("nsites", 0),
                            volume=None,
                            density=None,
                        ))

                    return materials

            except Exception as e:
                logger.warning("mp_search_error", elements=elements, error=str(e))
                return []

    async def get_phase_diagram_entries(
        self,
        elements: list[str],
    ) -> list[dict[str, Any]]:
        """Get phase diagram entries for a chemical system."""
        if not self._api_key:
            return []

        async with aiohttp.ClientSession() as session:
            try:
                headers = {"X-API-KEY": self._api_key}
                chemsys = "-".join(sorted(elements))
                url = f"{self._base_url}/materials/phase_diagram/{chemsys}"

                async with session.get(url, headers=headers, timeout=60) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    return data.get("data", [])

            except Exception as e:
                logger.warning("mp_phase_diagram_error", elements=elements, error=str(e))
                return []

    async def calculate_stability(
        self,
        composition: str,
        energy_per_atom: float,
    ) -> StabilityResult:
        """
        Calculate stability against Materials Project phase diagram.

        Args:
            composition: Chemical formula
            energy_per_atom: Energy per atom in eV

        Returns:
            StabilityResult with hull distance and decomposition
        """
        # Parse composition to get elements
        elements = self._parse_elements(composition)

        if not elements:
            return StabilityResult(
                energy_above_hull=0.0,
                stability_class=StabilityClass.UNKNOWN,
            )

        # Get competing phases
        materials = await self.search_by_elements(elements, max_results=50)

        if not materials:
            # No reference data - can't determine stability
            return StabilityResult(
                energy_above_hull=0.0,
                stability_class=StabilityClass.UNKNOWN,
            )

        # Find hull energy (simplified)
        # In production, would use proper convex hull calculation
        min_energy = min(m.energy_per_atom for m in materials if m.is_stable)

        energy_above_hull = max(0, energy_per_atom - min_energy)

        # Classify stability
        if energy_above_hull <= settings.stable_threshold:
            stability_class = StabilityClass.STABLE
            is_stable = True
            is_metastable = True
        elif energy_above_hull <= settings.hull_distance_threshold:
            stability_class = StabilityClass.METASTABLE
            is_stable = False
            is_metastable = True
        else:
            stability_class = StabilityClass.UNSTABLE
            is_stable = False
            is_metastable = False

        # Find competing phases
        competing = [m.formula_pretty for m in materials if m.is_stable][:5]

        return StabilityResult(
            energy_above_hull=energy_above_hull,
            stability_class=stability_class,
            is_stable=is_stable,
            is_metastable=is_metastable,
            competing_phases=competing,
        )

    def _parse_elements(self, composition: str) -> list[str]:
        """Parse element symbols from composition string."""
        import re

        # Match element symbols (capital letter followed by optional lowercase)
        pattern = r"([A-Z][a-z]?)"
        elements = re.findall(pattern, composition)
        return list(set(elements))

    async def find_similar_materials(
        self,
        composition: str,
        space_group: str | None = None,
        max_results: int = 10,
    ) -> list[SimilarMaterial]:
        """Find similar materials in Materials Project."""
        materials = await self.search_by_formula(composition, max_results=max_results)

        similar = []
        for mat in materials:
            similarity = 1.0  # Start with full similarity

            # Reduce similarity if space group doesn't match
            if space_group and mat.space_group:
                if mat.space_group != space_group:
                    similarity *= 0.7

            similar.append(SimilarMaterial(
                material_id=mat.material_id,
                formula=mat.formula_pretty,
                source_database="mp",
                space_group=mat.space_group,
                energy_above_hull=mat.energy_above_hull,
                structure_similarity=similarity,
                url=f"https://materialsproject.org/materials/{mat.material_id}",
            ))

        return similar
