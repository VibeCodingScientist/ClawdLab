"""Protein novelty checking with BLAST and Foldseek."""

import asyncio
import hashlib
import tempfile
from pathlib import Path
from typing import Any

from platform.verification_engines.compbio_verifier.base import (
    BaseCompBioVerifier,
    MCPToolProvider,
    NoveltyResult,
    ProteinStructure,
)
from platform.verification_engines.compbio_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ProteinNoveltyChecker(BaseCompBioVerifier):
    """
    Checks protein sequences and structures for novelty.

    Uses:
    - BLAST for sequence similarity search
    - Foldseek for structural similarity search
    - PDB and UniProt database queries
    - AlphaFold DB for predicted structures
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize novelty checker."""
        super().__init__(tool_provider)

    @property
    def component_name(self) -> str:
        return "novelty_checker"

    async def verify(
        self,
        sequence: str,
        structure: ProteinStructure | None = None,
        **kwargs,
    ) -> NoveltyResult:
        """Check novelty of a protein."""
        return await self.check_novelty(sequence, structure, **kwargs)

    async def check_novelty(
        self,
        sequence: str,
        structure: ProteinStructure | None = None,
        check_sequence: bool = True,
        check_structure: bool = True,
    ) -> NoveltyResult:
        """
        Check if a protein is novel.

        Args:
            sequence: Protein sequence
            structure: Optional protein structure
            check_sequence: Whether to run BLAST
            check_structure: Whether to run Foldseek

        Returns:
            NoveltyResult with novelty assessment
        """
        logger.info(
            "novelty_check_started",
            sequence_length=len(sequence),
            has_structure=structure is not None,
        )

        blast_hits = []
        foldseek_hits = []
        closest_pdb_id = None
        closest_uniprot_id = None
        sequence_identity = None
        structural_similarity = None

        # Run BLAST if requested
        if check_sequence:
            blast_result = await self._run_blast(sequence)
            blast_hits = blast_result.get("hits", [])

            if blast_hits:
                top_hit = blast_hits[0]
                sequence_identity = top_hit.get("identity", 0)
                closest_pdb_id = top_hit.get("pdb_id")
                closest_uniprot_id = top_hit.get("uniprot_id")

        # Run Foldseek if structure provided and requested
        if check_structure and structure and structure.pdb_string:
            foldseek_result = await self._run_foldseek(structure.pdb_string)
            foldseek_hits = foldseek_result.get("hits", [])

            if foldseek_hits:
                top_struct_hit = foldseek_hits[0]
                structural_similarity = top_struct_hit.get("tm_score", 0)
                if not closest_pdb_id:
                    closest_pdb_id = top_struct_hit.get("target_id")

        # Calculate novelty score
        novelty_score = self._calculate_novelty_score(
            sequence_identity=sequence_identity,
            structural_similarity=structural_similarity,
        )

        is_novel = novelty_score >= settings.novelty_min_score

        analysis = self._generate_analysis(
            sequence_identity=sequence_identity,
            structural_similarity=structural_similarity,
            blast_hits=blast_hits,
            foldseek_hits=foldseek_hits,
            novelty_score=novelty_score,
        )

        result = NoveltyResult(
            is_novel=is_novel,
            novelty_score=novelty_score,
            closest_pdb_id=closest_pdb_id,
            closest_uniprot_id=closest_uniprot_id,
            sequence_identity=sequence_identity,
            structural_similarity=structural_similarity,
            blast_hits=blast_hits[:10],
            foldseek_hits=foldseek_hits[:10],
            analysis=analysis,
        )

        logger.info(
            "novelty_check_completed",
            is_novel=is_novel,
            novelty_score=novelty_score,
            blast_hits_count=len(blast_hits),
            foldseek_hits_count=len(foldseek_hits),
        )

        return result

    async def _run_blast(self, sequence: str) -> dict[str, Any]:
        """Run BLAST search against protein databases."""
        # Check for MCP BLAST tool
        if await self._has_tool("blast_search"):
            return await self._invoke_tool(
                tool_name="blast_search",
                parameters={
                    "sequence": sequence,
                    "database": "pdb",
                    "evalue": settings.novelty_blast_evalue,
                    "max_hits": 50,
                },
            )

        # Check for MCP NCBI BLAST tool
        if await self._has_tool("ncbi_blast"):
            return await self._invoke_tool(
                tool_name="ncbi_blast",
                parameters={
                    "sequence": sequence,
                    "program": "blastp",
                    "database": "pdb",
                },
            )

        # Fall back to local BLAST
        return await self._run_local_blast(sequence)

    async def _run_local_blast(self, sequence: str) -> dict[str, Any]:
        """Run BLAST locally via container."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write query sequence
            query_file = Path(tmpdir) / "query.fasta"
            query_file.write_text(f">query\n{sequence}\n")

            output_file = Path(tmpdir) / "blast_output.json"

            cmd = [
                "blastp",
                "-query", str(query_file),
                "-db", "pdb",
                "-outfmt", "15",  # JSON output
                "-out", str(output_file),
                "-evalue", str(settings.novelty_blast_evalue),
                "-max_target_seqs", "50",
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                await asyncio.wait_for(
                    process.communicate(),
                    timeout=300,
                )

                if process.returncode != 0:
                    logger.warning("blast_failed")
                    return {"hits": []}

                # Parse BLAST JSON output
                import json
                result = json.loads(output_file.read_text())

                hits = []
                for hit in result.get("BlastOutput2", [{}])[0].get("report", {}).get("results", {}).get("search", {}).get("hits", []):
                    for hsp in hit.get("hsps", []):
                        hits.append({
                            "target_id": hit.get("description", [{}])[0].get("accession", ""),
                            "pdb_id": hit.get("description", [{}])[0].get("accession", "").split("_")[0],
                            "identity": hsp.get("identity", 0) / hsp.get("align_len", 1) * 100,
                            "evalue": hsp.get("evalue", 1.0),
                            "bit_score": hsp.get("bit_score", 0),
                            "align_length": hsp.get("align_len", 0),
                        })

                return {"hits": sorted(hits, key=lambda x: -x.get("bit_score", 0))}

            except Exception as e:
                logger.warning("blast_error", error=str(e))
                return {"hits": []}

    async def _run_foldseek(self, pdb_string: str) -> dict[str, Any]:
        """Run Foldseek structure search."""
        # Check for MCP Foldseek tool
        if await self._has_tool("foldseek_search"):
            return await self._invoke_tool(
                tool_name="foldseek_search",
                parameters={
                    "pdb_string": pdb_string,
                    "database": "pdb",
                    "tm_threshold": settings.novelty_foldseek_threshold,
                },
            )

        # Fall back to local Foldseek
        return await self._run_local_foldseek(pdb_string)

    async def _run_local_foldseek(self, pdb_string: str) -> dict[str, Any]:
        """Run Foldseek locally via container."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write query structure
            query_file = Path(tmpdir) / "query.pdb"
            query_file.write_text(pdb_string)

            output_file = Path(tmpdir) / "foldseek_output.tsv"

            cmd = [
                "foldseek", "easy-search",
                str(query_file),
                "/data/foldseek/pdb",  # Foldseek PDB database
                str(output_file),
                str(tmpdir),
                "--format-output", "query,target,tmscore,evalue,alntmscore",
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                await asyncio.wait_for(
                    process.communicate(),
                    timeout=300,
                )

                if process.returncode != 0:
                    logger.warning("foldseek_failed")
                    return {"hits": []}

                # Parse Foldseek TSV output
                hits = []
                if output_file.exists():
                    for line in output_file.read_text().strip().split("\n"):
                        if line:
                            parts = line.split("\t")
                            if len(parts) >= 5:
                                hits.append({
                                    "target_id": parts[1],
                                    "tm_score": float(parts[2]),
                                    "evalue": float(parts[3]),
                                    "aln_tm_score": float(parts[4]),
                                })

                return {"hits": sorted(hits, key=lambda x: -x.get("tm_score", 0))}

            except Exception as e:
                logger.warning("foldseek_error", error=str(e))
                return {"hits": []}

    def _calculate_novelty_score(
        self,
        sequence_identity: float | None,
        structural_similarity: float | None,
    ) -> float:
        """Calculate overall novelty score."""
        # Start with high novelty
        novelty = 1.0

        # Reduce based on sequence identity
        if sequence_identity is not None:
            # 100% identity = 0 novelty, 0% identity = full novelty
            seq_factor = 1.0 - (sequence_identity / 100.0)
            novelty = min(novelty, seq_factor)

        # Reduce based on structural similarity
        if structural_similarity is not None:
            # TM-score > 0.5 indicates similar fold
            # TM-score > 0.7 indicates very similar structure
            if structural_similarity > 0.5:
                struct_factor = 1.0 - structural_similarity
                novelty = min(novelty, struct_factor)

        return novelty

    def _generate_analysis(
        self,
        sequence_identity: float | None,
        structural_similarity: float | None,
        blast_hits: list[dict[str, Any]],
        foldseek_hits: list[dict[str, Any]],
        novelty_score: float,
    ) -> str:
        """Generate human-readable novelty analysis."""
        parts = []

        if novelty_score >= 0.9:
            parts.append("The protein appears to be highly novel with no close matches.")
        elif novelty_score >= 0.7:
            parts.append("The protein shows moderate novelty.")
        elif novelty_score >= 0.5:
            parts.append("The protein has some similarity to known proteins.")
        elif novelty_score >= 0.3:
            parts.append("The protein is similar to existing proteins.")
        else:
            parts.append("The protein closely resembles known proteins.")

        if sequence_identity is not None and sequence_identity > 30:
            parts.append(f"Highest sequence identity: {sequence_identity:.1f}%.")

        if structural_similarity is not None and structural_similarity > 0.5:
            parts.append(f"Structural TM-score to closest match: {structural_similarity:.2f}.")

        if blast_hits:
            parts.append(f"Found {len(blast_hits)} BLAST hits.")

        if foldseek_hits:
            parts.append(f"Found {len(foldseek_hits)} structural matches.")

        return " ".join(parts)

    async def search_pdb(self, sequence: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Search PDB for similar structures."""
        # Check for MCP PDB search tool
        if await self._has_tool("pdb_search"):
            result = await self._invoke_tool(
                tool_name="pdb_search",
                parameters={
                    "sequence": sequence,
                    "max_results": max_results,
                },
            )
            return result.get("entries", [])

        # Fall back to BLAST against PDB
        blast_result = await self._run_blast(sequence)
        return [
            {
                "pdb_id": hit.get("pdb_id"),
                "identity": hit.get("identity"),
                "evalue": hit.get("evalue"),
            }
            for hit in blast_result.get("hits", [])[:max_results]
        ]

    async def search_uniprot(self, sequence: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Search UniProt for similar sequences."""
        # Check for MCP UniProt search tool
        if await self._has_tool("uniprot_search"):
            result = await self._invoke_tool(
                tool_name="uniprot_search",
                parameters={
                    "sequence": sequence,
                    "max_results": max_results,
                },
            )
            return result.get("entries", [])

        # Placeholder - in production would query UniProt API
        return []

    async def check_alphafold_db(self, uniprot_id: str) -> dict[str, Any] | None:
        """Check if structure exists in AlphaFold Database."""
        # Check for MCP AlphaFold DB tool
        if await self._has_tool("alphafold_db_fetch"):
            try:
                result = await self._invoke_tool(
                    tool_name="alphafold_db_fetch",
                    parameters={
                        "uniprot_id": uniprot_id,
                    },
                )
                return result
            except Exception:
                return None

        # Placeholder - in production would query AlphaFold DB API
        return None
