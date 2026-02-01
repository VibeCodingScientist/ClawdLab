"""Database integrations for PDB, UniProt, and AlphaFold DB."""

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from platform.verification_engines.compbio_verifier.base import (
    MCPToolProvider,
    ProteinStructure,
)
from platform.verification_engines.compbio_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class PDBEntry:
    """Entry from PDB database."""

    pdb_id: str
    title: str
    resolution: float | None
    method: str
    organism: str | None
    sequence: str | None
    chains: list[str]
    release_date: str | None
    pdb_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pdb_id": self.pdb_id,
            "title": self.title,
            "resolution": self.resolution,
            "method": self.method,
            "organism": self.organism,
            "sequence": self.sequence,
            "chains": self.chains,
            "release_date": self.release_date,
            "pdb_url": self.pdb_url,
        }


@dataclass
class UniProtEntry:
    """Entry from UniProt database."""

    accession: str
    entry_name: str
    protein_name: str
    organism: str
    sequence: str
    length: int
    function: str | None
    subcellular_location: list[str]
    pdb_cross_refs: list[str]
    alphafold_available: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "accession": self.accession,
            "entry_name": self.entry_name,
            "protein_name": self.protein_name,
            "organism": self.organism,
            "sequence": self.sequence,
            "length": self.length,
            "function": self.function,
            "subcellular_location": self.subcellular_location,
            "pdb_cross_refs": self.pdb_cross_refs,
            "alphafold_available": self.alphafold_available,
        }


class PDBClient:
    """Client for RCSB PDB REST API."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize PDB client."""
        self._base_url = settings.pdb_api_url
        self._tool_provider = tool_provider

    async def get_entry(self, pdb_id: str) -> PDBEntry | None:
        """Get PDB entry by ID."""
        # Check for MCP tool
        if self._tool_provider and await self._tool_provider.has_tool("pdb_fetch"):
            result = await self._tool_provider.invoke_tool(
                tool_name="pdb_fetch",
                parameters={"pdb_id": pdb_id},
            )
            if result:
                return PDBEntry(**result)

        # Use REST API
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self._base_url}/core/entry/{pdb_id.upper()}"
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()

                    return PDBEntry(
                        pdb_id=pdb_id.upper(),
                        title=data.get("struct", {}).get("title", ""),
                        resolution=data.get("rcsb_entry_info", {}).get("resolution_combined", [None])[0],
                        method=data.get("exptl", [{}])[0].get("method", ""),
                        organism=data.get("rcsb_entry_info", {}).get("deposited_organism_lineage", [{}])[0].get("name"),
                        sequence=None,  # Would need separate query
                        chains=list(data.get("rcsb_entry_container_identifiers", {}).get("entity_ids", [])),
                        release_date=data.get("rcsb_accession_info", {}).get("initial_release_date"),
                        pdb_url=f"https://www.rcsb.org/structure/{pdb_id.upper()}",
                    )

            except Exception as e:
                logger.warning("pdb_fetch_error", pdb_id=pdb_id, error=str(e))
                return None

    async def get_structure(self, pdb_id: str, format: str = "pdb") -> str | None:
        """Download PDB structure file."""
        async with aiohttp.ClientSession() as session:
            try:
                if format == "pdb":
                    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
                elif format == "cif":
                    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.cif"
                else:
                    return None

                async with session.get(url, timeout=60) as response:
                    if response.status != 200:
                        return None
                    return await response.text()

            except Exception as e:
                logger.warning("pdb_download_error", pdb_id=pdb_id, error=str(e))
                return None

    async def search_sequence(
        self,
        sequence: str,
        identity_cutoff: float = 0.9,
        max_results: int = 10,
    ) -> list[PDBEntry]:
        """Search PDB by sequence."""
        async with aiohttp.ClientSession() as session:
            try:
                url = "https://search.rcsb.org/rcsbsearch/v2/query"
                query = {
                    "query": {
                        "type": "terminal",
                        "service": "sequence",
                        "parameters": {
                            "target": "pdb_protein_sequence",
                            "value": sequence,
                            "identity_cutoff": identity_cutoff,
                        },
                    },
                    "return_type": "entry",
                    "request_options": {
                        "results_content_type": ["experimental"],
                        "return_all_hits": False,
                        "pager": {"start": 0, "rows": max_results},
                    },
                }

                async with session.post(url, json=query, timeout=60) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    entries = []

                    for hit in data.get("result_set", []):
                        pdb_id = hit.get("identifier")
                        if pdb_id:
                            entry = await self.get_entry(pdb_id)
                            if entry:
                                entries.append(entry)

                    return entries

            except Exception as e:
                logger.warning("pdb_search_error", error=str(e))
                return []


class UniProtClient:
    """Client for UniProt REST API."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize UniProt client."""
        self._base_url = settings.uniprot_api_url
        self._tool_provider = tool_provider

    async def get_entry(self, accession: str) -> UniProtEntry | None:
        """Get UniProt entry by accession."""
        # Check for MCP tool
        if self._tool_provider and await self._tool_provider.has_tool("uniprot_fetch"):
            result = await self._tool_provider.invoke_tool(
                tool_name="uniprot_fetch",
                parameters={"accession": accession},
            )
            if result:
                return UniProtEntry(**result)

        # Use REST API
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self._base_url}/uniprotkb/{accession}.json"
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()

                    # Extract sequence
                    sequence = data.get("sequence", {}).get("value", "")

                    # Extract protein name
                    protein_name = ""
                    if "proteinDescription" in data:
                        rec_name = data["proteinDescription"].get("recommendedName", {})
                        protein_name = rec_name.get("fullName", {}).get("value", "")

                    # Extract function
                    function = None
                    for comment in data.get("comments", []):
                        if comment.get("commentType") == "FUNCTION":
                            texts = comment.get("texts", [])
                            if texts:
                                function = texts[0].get("value")
                            break

                    # Extract subcellular location
                    locations = []
                    for comment in data.get("comments", []):
                        if comment.get("commentType") == "SUBCELLULAR LOCATION":
                            for loc in comment.get("subcellularLocations", []):
                                loc_val = loc.get("location", {}).get("value")
                                if loc_val:
                                    locations.append(loc_val)

                    # Extract PDB cross-references
                    pdb_refs = []
                    for xref in data.get("uniProtKBCrossReferences", []):
                        if xref.get("database") == "PDB":
                            pdb_refs.append(xref.get("id"))

                    # Check AlphaFold availability
                    alphafold_available = any(
                        xref.get("database") == "AlphaFoldDB"
                        for xref in data.get("uniProtKBCrossReferences", [])
                    )

                    return UniProtEntry(
                        accession=accession,
                        entry_name=data.get("uniProtkbId", ""),
                        protein_name=protein_name,
                        organism=data.get("organism", {}).get("scientificName", ""),
                        sequence=sequence,
                        length=len(sequence),
                        function=function,
                        subcellular_location=locations,
                        pdb_cross_refs=pdb_refs,
                        alphafold_available=alphafold_available,
                    )

            except Exception as e:
                logger.warning("uniprot_fetch_error", accession=accession, error=str(e))
                return None

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[UniProtEntry]:
        """Search UniProt with query string."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self._base_url}/uniprotkb/search"
                params = {
                    "query": query,
                    "format": "json",
                    "size": max_results,
                }

                async with session.get(url, params=params, timeout=60) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    entries = []

                    for result in data.get("results", []):
                        accession = result.get("primaryAccession")
                        if accession:
                            entry = await self.get_entry(accession)
                            if entry:
                                entries.append(entry)

                    return entries

            except Exception as e:
                logger.warning("uniprot_search_error", error=str(e))
                return []


class AlphaFoldDBClient:
    """Client for AlphaFold Database API."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize AlphaFold DB client."""
        self._base_url = settings.alphafold_db_url
        self._tool_provider = tool_provider

    async def get_prediction(self, uniprot_id: str) -> ProteinStructure | None:
        """Get AlphaFold prediction for UniProt ID."""
        # Check for MCP tool
        if self._tool_provider and await self._tool_provider.has_tool("alphafold_db_fetch"):
            result = await self._tool_provider.invoke_tool(
                tool_name="alphafold_db_fetch",
                parameters={"uniprot_id": uniprot_id},
            )
            if result:
                return ProteinStructure(
                    sequence=result.get("sequence", ""),
                    pdb_string=result.get("pdb_string"),
                    mean_plddt=result.get("mean_plddt", 0.0),
                    model_used="alphafold_db",
                )

        # Use REST API
        async with aiohttp.ClientSession() as session:
            try:
                # Get prediction info
                url = f"{self._base_url}/prediction/{uniprot_id}"
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()

                    if not data:
                        return None

                    prediction = data[0] if isinstance(data, list) else data

                # Download PDB file
                pdb_url = prediction.get("pdbUrl")
                if pdb_url:
                    async with session.get(pdb_url, timeout=60) as pdb_response:
                        if pdb_response.status == 200:
                            pdb_string = await pdb_response.text()
                        else:
                            pdb_string = None
                else:
                    pdb_string = None

                return ProteinStructure(
                    sequence=prediction.get("uniprotSequence", ""),
                    pdb_string=pdb_string,
                    mean_plddt=prediction.get("globalMetricValue", 0.0),
                    model_used="alphafold_db",
                )

            except Exception as e:
                logger.warning("alphafold_db_error", uniprot_id=uniprot_id, error=str(e))
                return None

    async def check_availability(self, uniprot_id: str) -> bool:
        """Check if AlphaFold prediction is available."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self._base_url}/prediction/{uniprot_id}"
                async with session.head(url, timeout=10) as response:
                    return response.status == 200
            except Exception:
                return False


class DatabaseManager:
    """Unified manager for all database integrations."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize database manager."""
        self.pdb = PDBClient(tool_provider)
        self.uniprot = UniProtClient(tool_provider)
        self.alphafold_db = AlphaFoldDBClient(tool_provider)

    async def find_structure(
        self,
        sequence: str | None = None,
        uniprot_id: str | None = None,
        pdb_id: str | None = None,
    ) -> ProteinStructure | None:
        """
        Find best available structure for a protein.

        Tries PDB first, then AlphaFold DB.
        """
        # If PDB ID provided, get experimental structure
        if pdb_id:
            pdb_string = await self.pdb.get_structure(pdb_id)
            if pdb_string:
                entry = await self.pdb.get_entry(pdb_id)
                return ProteinStructure(
                    sequence=entry.sequence or "",
                    pdb_string=pdb_string,
                    model_used=f"pdb:{pdb_id}",
                )

        # If UniProt ID provided, check AlphaFold DB
        if uniprot_id:
            af_struct = await self.alphafold_db.get_prediction(uniprot_id)
            if af_struct:
                return af_struct

        # If sequence provided, search PDB
        if sequence:
            pdb_entries = await self.pdb.search_sequence(sequence, max_results=1)
            if pdb_entries:
                pdb_string = await self.pdb.get_structure(pdb_entries[0].pdb_id)
                if pdb_string:
                    return ProteinStructure(
                        sequence=sequence,
                        pdb_string=pdb_string,
                        model_used=f"pdb:{pdb_entries[0].pdb_id}",
                    )

        return None

    async def get_protein_info(
        self,
        uniprot_id: str,
    ) -> dict[str, Any]:
        """Get comprehensive protein information."""
        info = {
            "uniprot": None,
            "pdb_structures": [],
            "alphafold_prediction": None,
        }

        # Get UniProt entry
        uniprot_entry = await self.uniprot.get_entry(uniprot_id)
        if uniprot_entry:
            info["uniprot"] = uniprot_entry.to_dict()

            # Get PDB structures
            for pdb_id in uniprot_entry.pdb_cross_refs[:5]:
                pdb_entry = await self.pdb.get_entry(pdb_id)
                if pdb_entry:
                    info["pdb_structures"].append(pdb_entry.to_dict())

            # Get AlphaFold prediction
            if uniprot_entry.alphafold_available:
                af_struct = await self.alphafold_db.get_prediction(uniprot_id)
                if af_struct:
                    info["alphafold_prediction"] = af_struct.to_dict()

        return info
