"""Crystal structure analysis and validation tools."""

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any

from platform.verification_engines.materials_verifier.base import (
    AtomSite,
    BaseMaterialsVerifier,
    CrystalStructure,
    CrystalSystem,
    LatticeParameters,
    MCPToolProvider,
)
from platform.verification_engines.materials_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CIFParser:
    """Parser for Crystallographic Information Files (CIF)."""

    def __init__(self):
        """Initialize CIF parser."""
        self._lattice_keys = {
            "_cell_length_a": "a",
            "_cell_length_b": "b",
            "_cell_length_c": "c",
            "_cell_angle_alpha": "alpha",
            "_cell_angle_beta": "beta",
            "_cell_angle_gamma": "gamma",
        }

    def parse(self, cif_content: str) -> CrystalStructure:
        """
        Parse CIF string into CrystalStructure.

        Args:
            cif_content: CIF file content as string

        Returns:
            Parsed CrystalStructure object
        """
        lines = cif_content.strip().split("\n")

        # Extract lattice parameters
        lattice_values = {}
        for line in lines:
            line = line.strip()
            for cif_key, param_name in self._lattice_keys.items():
                if line.startswith(cif_key):
                    value = self._extract_value(line)
                    if value is not None:
                        lattice_values[param_name] = value

        # Extract space group
        space_group = None
        space_group_number = None
        for line in lines:
            if "_symmetry_space_group_name_H-M" in line or "_space_group_name_H-M_alt" in line:
                space_group = self._extract_string_value(line)
            if "_symmetry_Int_Tables_number" in line or "_space_group_IT_number" in line:
                val = self._extract_value(line)
                if val:
                    space_group_number = int(val)

        # Extract composition
        composition = self._extract_composition(lines)

        # Extract atomic sites
        sites = self._extract_sites(lines)

        # Determine crystal system from space group
        crystal_system = self._determine_crystal_system(space_group_number)

        # Build lattice parameters
        lattice = LatticeParameters(
            a=lattice_values.get("a", 1.0),
            b=lattice_values.get("b", 1.0),
            c=lattice_values.get("c", 1.0),
            alpha=lattice_values.get("alpha", 90.0),
            beta=lattice_values.get("beta", 90.0),
            gamma=lattice_values.get("gamma", 90.0),
        )

        return CrystalStructure(
            composition=composition,
            lattice=lattice,
            sites=sites,
            space_group=space_group,
            space_group_number=space_group_number,
            crystal_system=crystal_system,
            cif_string=cif_content,
            source="cif_parse",
        )

    def _extract_value(self, line: str) -> float | None:
        """Extract numeric value from CIF line."""
        parts = line.split()
        if len(parts) >= 2:
            value_str = parts[1]
            # Remove uncertainty in parentheses
            value_str = re.sub(r"\([^)]*\)", "", value_str)
            try:
                return float(value_str)
            except ValueError:
                return None
        return None

    def _extract_string_value(self, line: str) -> str | None:
        """Extract string value from CIF line."""
        parts = line.split(maxsplit=1)
        if len(parts) >= 2:
            value = parts[1].strip()
            # Remove quotes
            value = value.strip("'\"")
            return value
        return None

    def _extract_composition(self, lines: list[str]) -> str:
        """Extract chemical composition from CIF."""
        for line in lines:
            if "_chemical_formula_sum" in line:
                return self._extract_string_value(line) or ""
            if "_chemical_formula_structural" in line:
                return self._extract_string_value(line) or ""
        return ""

    def _extract_sites(self, lines: list[str]) -> list[AtomSite]:
        """Extract atomic sites from CIF."""
        sites = []

        # Find loop_ for atom sites
        in_atom_loop = False
        loop_keys = []
        key_indices = {}

        for i, line in enumerate(lines):
            line = line.strip()

            if line == "loop_":
                in_atom_loop = False
                loop_keys = []
                key_indices = {}
                continue

            if line.startswith("_atom_site_"):
                in_atom_loop = True
                loop_keys.append(line)
                if "_atom_site_type_symbol" in line or "_atom_site_label" in line:
                    key_indices["species"] = len(loop_keys) - 1
                elif "_atom_site_fract_x" in line:
                    key_indices["x"] = len(loop_keys) - 1
                elif "_atom_site_fract_y" in line:
                    key_indices["y"] = len(loop_keys) - 1
                elif "_atom_site_fract_z" in line:
                    key_indices["z"] = len(loop_keys) - 1
                elif "_atom_site_occupancy" in line:
                    key_indices["occupancy"] = len(loop_keys) - 1
                elif "_atom_site_Wyckoff_symbol" in line:
                    key_indices["wyckoff"] = len(loop_keys) - 1
                continue

            if in_atom_loop and not line.startswith("_") and not line.startswith("loop_") and line:
                # Parse atom site data
                parts = line.split()
                if len(parts) >= len(loop_keys):
                    try:
                        species = parts[key_indices.get("species", 0)] if "species" in key_indices else "X"
                        # Clean species (remove numbers from labels like "Fe1")
                        species = re.sub(r"\d+$", "", species)

                        x = float(parts[key_indices["x"]]) if "x" in key_indices else 0.0
                        y = float(parts[key_indices["y"]]) if "y" in key_indices else 0.0
                        z = float(parts[key_indices["z"]]) if "z" in key_indices else 0.0
                        occupancy = float(parts[key_indices["occupancy"]]) if "occupancy" in key_indices else 1.0
                        wyckoff = parts[key_indices["wyckoff"]] if "wyckoff" in key_indices else None

                        sites.append(AtomSite(
                            species=species,
                            x=x,
                            y=y,
                            z=z,
                            occupancy=occupancy,
                            wyckoff=wyckoff,
                        ))
                    except (ValueError, IndexError):
                        continue

            if in_atom_loop and (line.startswith("loop_") or line.startswith("_") and not line.startswith("_atom_site")):
                in_atom_loop = False

        return sites

    def _determine_crystal_system(self, space_group_number: int | None) -> CrystalSystem | None:
        """Determine crystal system from space group number."""
        if space_group_number is None:
            return None

        if 1 <= space_group_number <= 2:
            return CrystalSystem.TRICLINIC
        elif 3 <= space_group_number <= 15:
            return CrystalSystem.MONOCLINIC
        elif 16 <= space_group_number <= 74:
            return CrystalSystem.ORTHORHOMBIC
        elif 75 <= space_group_number <= 142:
            return CrystalSystem.TETRAGONAL
        elif 143 <= space_group_number <= 167:
            return CrystalSystem.TRIGONAL
        elif 168 <= space_group_number <= 194:
            return CrystalSystem.HEXAGONAL
        elif 195 <= space_group_number <= 230:
            return CrystalSystem.CUBIC
        return None


class StructureValidator(BaseMaterialsVerifier):
    """Validator for crystal structure physical plausibility."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize structure validator."""
        super().__init__(tool_provider)
        self._cif_parser = CIFParser()

    @property
    def component_name(self) -> str:
        return "structure_validator"

    async def verify(
        self,
        structure: CrystalStructure,
    ) -> dict[str, Any]:
        """Validate crystal structure."""
        return await self.validate_structure(structure)

    async def validate_structure(
        self,
        structure: CrystalStructure,
    ) -> dict[str, Any]:
        """
        Validate crystal structure for physical plausibility.

        Args:
            structure: Crystal structure to validate

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        # Check lattice parameters
        lattice_valid, lattice_issues = self._validate_lattice(structure.lattice)
        if not lattice_valid:
            issues.extend(lattice_issues)

        # Check atomic distances
        distance_valid, distance_issues = await self._validate_distances(structure)
        if not distance_valid:
            issues.extend(distance_issues)

        # Check volume per atom
        volume_valid, volume_warnings = self._validate_volume(structure)
        if not volume_valid:
            warnings.extend(volume_warnings)

        # Check occupancies
        occupancy_valid, occupancy_warnings = self._validate_occupancies(structure)
        if not occupancy_valid:
            warnings.extend(occupancy_warnings)

        # Check for overlapping atoms
        overlap_valid, overlap_issues = self._check_overlapping_atoms(structure)
        if not overlap_valid:
            issues.extend(overlap_issues)

        is_valid = len(issues) == 0

        return {
            "valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "num_atoms": structure.num_atoms,
            "volume": structure.lattice.volume,
            "volume_per_atom": structure.volume_per_atom,
        }

    def _validate_lattice(self, lattice: LatticeParameters) -> tuple[bool, list[str]]:
        """Validate lattice parameters."""
        issues = []

        # Check positive lengths
        if lattice.a <= 0:
            issues.append(f"Invalid lattice parameter a: {lattice.a}")
        if lattice.b <= 0:
            issues.append(f"Invalid lattice parameter b: {lattice.b}")
        if lattice.c <= 0:
            issues.append(f"Invalid lattice parameter c: {lattice.c}")

        # Check angles
        for angle_name, angle_value in [("alpha", lattice.alpha), ("beta", lattice.beta), ("gamma", lattice.gamma)]:
            if angle_value <= 0 or angle_value >= 180:
                issues.append(f"Invalid angle {angle_name}: {angle_value}")

        # Check reasonable ranges
        if lattice.a > 100 or lattice.b > 100 or lattice.c > 100:
            issues.append("Unusually large lattice parameters (>100 Å)")

        return len(issues) == 0, issues

    async def _validate_distances(self, structure: CrystalStructure) -> tuple[bool, list[str]]:
        """Validate interatomic distances."""
        issues = []

        if len(structure.sites) < 2:
            return True, []

        # Try MCP tool first
        if await self._has_tool("calculate_distances"):
            result = await self._invoke_tool(
                "calculate_distances",
                {"cif_string": structure.cif_string},
            )
            min_dist = result.get("min_distance", float("inf"))
        else:
            # Calculate locally
            min_dist = self._calculate_min_distance(structure)

        if min_dist < settings.min_distance_threshold:
            issues.append(f"Atoms too close: minimum distance {min_dist:.3f} Å < {settings.min_distance_threshold} Å")

        return len(issues) == 0, issues

    def _calculate_min_distance(self, structure: CrystalStructure) -> float:
        """Calculate minimum interatomic distance."""
        import math

        min_dist = float("inf")
        lattice = structure.lattice

        # Convert fractional to Cartesian (simplified, assumes orthogonal)
        def frac_to_cart(x, y, z):
            return (
                x * lattice.a,
                y * lattice.b,
                z * lattice.c,
            )

        for i, site1 in enumerate(structure.sites):
            cart1 = frac_to_cart(site1.x, site1.y, site1.z)
            for j, site2 in enumerate(structure.sites[i + 1:], i + 1):
                cart2 = frac_to_cart(site2.x, site2.y, site2.z)

                # Check distance with periodic images
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        for dz in [-1, 0, 1]:
                            cart2_img = (
                                cart2[0] + dx * lattice.a,
                                cart2[1] + dy * lattice.b,
                                cart2[2] + dz * lattice.c,
                            )
                            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(cart1, cart2_img)))
                            if dist > 0:
                                min_dist = min(min_dist, dist)

        return min_dist

    def _validate_volume(self, structure: CrystalStructure) -> tuple[bool, list[str]]:
        """Validate volume per atom."""
        warnings = []

        if structure.volume_per_atom > settings.max_volume_per_atom:
            warnings.append(
                f"Large volume per atom: {structure.volume_per_atom:.1f} Å³ > {settings.max_volume_per_atom} Å³"
            )

        if structure.volume_per_atom < 5.0:
            warnings.append(f"Small volume per atom: {structure.volume_per_atom:.1f} Å³")

        return len(warnings) == 0, warnings

    def _validate_occupancies(self, structure: CrystalStructure) -> tuple[bool, list[str]]:
        """Validate site occupancies."""
        warnings = []

        for i, site in enumerate(structure.sites):
            if site.occupancy < 0 or site.occupancy > 1:
                warnings.append(f"Invalid occupancy at site {i}: {site.occupancy}")
            elif site.occupancy < 1.0:
                warnings.append(f"Partial occupancy at site {i}: {site.occupancy}")

        return len(warnings) == 0, warnings

    def _check_overlapping_atoms(self, structure: CrystalStructure) -> tuple[bool, list[str]]:
        """Check for overlapping atoms (same position)."""
        issues = []
        tolerance = 0.01  # Å

        seen_positions = []
        for i, site in enumerate(structure.sites):
            pos = (site.x, site.y, site.z)
            for j, seen in enumerate(seen_positions):
                if all(abs(a - b) < tolerance for a, b in zip(pos, seen)):
                    issues.append(f"Overlapping atoms at sites {j} and {i}")
            seen_positions.append(pos)

        return len(issues) == 0, issues


class SymmetryAnalyzer(BaseMaterialsVerifier):
    """Symmetry analysis for crystal structures."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize symmetry analyzer."""
        super().__init__(tool_provider)

    @property
    def component_name(self) -> str:
        return "symmetry_analyzer"

    async def verify(
        self,
        structure: CrystalStructure,
    ) -> dict[str, Any]:
        """Analyze structure symmetry."""
        return await self.analyze_symmetry(structure)

    async def analyze_symmetry(
        self,
        structure: CrystalStructure,
        symprec: float | None = None,
    ) -> dict[str, Any]:
        """
        Analyze crystal symmetry using spglib.

        Args:
            structure: Crystal structure
            symprec: Symmetry precision tolerance

        Returns:
            Dict with symmetry analysis results
        """
        symprec = symprec or settings.symmetry_tolerance

        # Try MCP tool first
        if await self._has_tool("analyze_symmetry"):
            result = await self._invoke_tool(
                "analyze_symmetry",
                {"cif_string": structure.cif_string, "symprec": symprec},
            )
            return result

        # Fall back to local calculation
        return await self._analyze_locally(structure, symprec)

    async def _analyze_locally(
        self,
        structure: CrystalStructure,
        symprec: float,
    ) -> dict[str, Any]:
        """Run symmetry analysis locally via subprocess."""
        if not structure.cif_string:
            return {"error": "No CIF string available"}

        with tempfile.TemporaryDirectory() as tmpdir:
            cif_path = Path(tmpdir) / "structure.cif"
            cif_path.write_text(structure.cif_string)

            script = f"""
import json
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

structure = Structure.from_file("{cif_path}")
analyzer = SpacegroupAnalyzer(structure, symprec={symprec})

result = {{
    "space_group_symbol": analyzer.get_space_group_symbol(),
    "space_group_number": analyzer.get_space_group_number(),
    "crystal_system": analyzer.get_crystal_system(),
    "point_group": analyzer.get_point_group_symbol(),
    "hall_symbol": analyzer.get_hall(),
    "is_primitive": analyzer.is_laue(),
}}

# Get Wyckoff positions
wyckoff_sets = analyzer.get_symmetrized_structure().wyckoff_symbols
result["wyckoff_positions"] = wyckoff_sets

print(json.dumps(result))
"""
            script_path = Path(tmpdir) / "analyze.py"
            script_path.write_text(script)

            if settings.use_singularity:
                cmd = [
                    "singularity", "exec",
                    settings.singularity_image_path,
                    "python", str(script_path),
                ]
            else:
                cmd = ["python", str(script_path)]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=60,
                )

                if process.returncode != 0:
                    return {"error": f"Symmetry analysis failed: {stderr.decode()}"}

                import json
                return json.loads(stdout.decode())

            except asyncio.TimeoutError:
                return {"error": "Symmetry analysis timed out"}
            except Exception as e:
                logger.warning("symmetry_analysis_error", error=str(e))
                return {"error": str(e)}

    async def compare_symmetry(
        self,
        structure: CrystalStructure,
        claimed_space_group: str | None = None,
        claimed_crystal_system: str | None = None,
    ) -> dict[str, Any]:
        """
        Compare analyzed symmetry with claimed values.

        Args:
            structure: Crystal structure
            claimed_space_group: Claimed space group symbol
            claimed_crystal_system: Claimed crystal system

        Returns:
            Dict with comparison results
        """
        analysis = await self.analyze_symmetry(structure)

        if "error" in analysis:
            return analysis

        result = {
            "analyzed_space_group": analysis.get("space_group_symbol"),
            "analyzed_crystal_system": analysis.get("crystal_system"),
            "space_group_match": True,
            "crystal_system_match": True,
        }

        if claimed_space_group:
            result["claimed_space_group"] = claimed_space_group
            # Normalize and compare
            analyzed_sg = analysis.get("space_group_symbol", "").replace(" ", "")
            claimed_sg = claimed_space_group.replace(" ", "")
            result["space_group_match"] = analyzed_sg == claimed_sg

        if claimed_crystal_system:
            result["claimed_crystal_system"] = claimed_crystal_system
            analyzed_cs = analysis.get("crystal_system", "").lower()
            claimed_cs = claimed_crystal_system.lower()
            result["crystal_system_match"] = analyzed_cs == claimed_cs

        result["symmetry_verified"] = result["space_group_match"] and result["crystal_system_match"]

        return result


class StructureComparator:
    """Compare crystal structures for similarity."""

    async def compare_structures(
        self,
        structure1: CrystalStructure,
        structure2: CrystalStructure,
        ltol: float = 0.2,
        stol: float = 0.3,
        angle_tol: float = 5.0,
    ) -> dict[str, Any]:
        """
        Compare two crystal structures.

        Args:
            structure1: First structure
            structure2: Second structure
            ltol: Fractional length tolerance
            stol: Site tolerance
            angle_tol: Angle tolerance in degrees

        Returns:
            Dict with comparison results
        """
        # Compare compositions
        comp_match = structure1.composition == structure2.composition

        # Compare lattice parameters
        lattice_similar = self._compare_lattices(
            structure1.lattice, structure2.lattice, ltol, angle_tol
        )

        # Compare space groups
        sg_match = (
            structure1.space_group == structure2.space_group
            if structure1.space_group and structure2.space_group
            else None
        )

        # Calculate overall similarity score
        similarity = 0.0
        if comp_match:
            similarity += 0.4
        if lattice_similar:
            similarity += 0.3
        if sg_match:
            similarity += 0.3

        return {
            "composition_match": comp_match,
            "lattice_similar": lattice_similar,
            "space_group_match": sg_match,
            "similarity_score": similarity,
            "is_same_structure": comp_match and lattice_similar and (sg_match or sg_match is None),
        }

    def _compare_lattices(
        self,
        lattice1: LatticeParameters,
        lattice2: LatticeParameters,
        ltol: float,
        angle_tol: float,
    ) -> bool:
        """Compare two lattices within tolerance."""
        # Compare lengths (fractional tolerance)
        for name in ["a", "b", "c"]:
            v1 = getattr(lattice1, name)
            v2 = getattr(lattice2, name)
            if abs(v1 - v2) / max(v1, v2) > ltol:
                return False

        # Compare angles (absolute tolerance)
        for name in ["alpha", "beta", "gamma"]:
            v1 = getattr(lattice1, name)
            v2 = getattr(lattice2, name)
            if abs(v1 - v2) > angle_tol:
                return False

        return True


def parse_cif(cif_content: str) -> CrystalStructure:
    """Parse CIF string into CrystalStructure."""
    parser = CIFParser()
    return parser.parse(cif_content)
