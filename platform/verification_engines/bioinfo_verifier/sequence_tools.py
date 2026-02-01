"""Sequence analysis tools for bioinformatics verification."""

import asyncio
import gzip
import re
import tempfile
from pathlib import Path
from typing import Any, Iterator

from platform.verification_engines.bioinfo_verifier.base import (
    AlignmentResult,
    BaseBioinfoVerifier,
    MCPToolProvider,
    SequenceInfo,
    VariantCall,
)
from platform.verification_engines.bioinfo_verifier.config import (
    SEQUENCE_FORMATS,
    get_settings,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class FastaParser:
    """Parser for FASTA format files."""

    def parse(self, content: str) -> Iterator[SequenceInfo]:
        """
        Parse FASTA content.

        Args:
            content: FASTA format string

        Yields:
            SequenceInfo for each sequence
        """
        current_id = None
        current_desc = ""
        current_seq = []

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith(">"):
                # Save previous sequence
                if current_id and current_seq:
                    seq = "".join(current_seq)
                    yield SequenceInfo(
                        sequence_id=current_id,
                        length=len(seq),
                        sequence_type=self._detect_type(seq),
                        gc_content=self._calculate_gc(seq),
                        description=current_desc,
                    )

                # Parse new header
                header = line[1:].strip()
                parts = header.split(None, 1)
                current_id = parts[0] if parts else ""
                current_desc = parts[1] if len(parts) > 1 else ""
                current_seq = []
            else:
                current_seq.append(line)

        # Yield last sequence
        if current_id and current_seq:
            seq = "".join(current_seq)
            yield SequenceInfo(
                sequence_id=current_id,
                length=len(seq),
                sequence_type=self._detect_type(seq),
                gc_content=self._calculate_gc(seq),
                description=current_desc,
            )

    def _detect_type(self, sequence: str) -> str:
        """Detect sequence type."""
        seq_upper = sequence.upper()
        dna_chars = set("ATCGN")
        rna_chars = set("AUCGN")
        protein_chars = set("ACDEFGHIKLMNPQRSTVWY*")

        if set(seq_upper) <= dna_chars:
            return "dna"
        elif set(seq_upper) <= rna_chars:
            return "rna"
        elif set(seq_upper) <= protein_chars:
            return "protein"
        return "unknown"

    def _calculate_gc(self, sequence: str) -> float | None:
        """Calculate GC content for DNA/RNA."""
        seq_upper = sequence.upper()
        if set(seq_upper) - set("ATCGUN"):
            return None  # Not nucleic acid

        gc = seq_upper.count("G") + seq_upper.count("C")
        total = len(seq_upper.replace("N", ""))

        return (gc / total * 100) if total > 0 else None


class FastqParser:
    """Parser for FASTQ format files."""

    def parse(self, content: str) -> Iterator[tuple[SequenceInfo, str]]:
        """
        Parse FASTQ content.

        Args:
            content: FASTQ format string

        Yields:
            Tuple of (SequenceInfo, quality_string)
        """
        lines = content.strip().split("\n")
        i = 0

        while i < len(lines):
            if not lines[i].startswith("@"):
                i += 1
                continue

            header = lines[i][1:].strip()
            parts = header.split(None, 1)
            seq_id = parts[0] if parts else ""

            sequence = lines[i + 1].strip() if i + 1 < len(lines) else ""
            quality = lines[i + 3].strip() if i + 3 < len(lines) else ""

            yield (
                SequenceInfo(
                    sequence_id=seq_id,
                    length=len(sequence),
                    sequence_type="dna",
                    description=parts[1] if len(parts) > 1 else "",
                ),
                quality,
            )

            i += 4


class VCFParser:
    """Parser for VCF format files."""

    def parse(self, content: str) -> Iterator[VariantCall]:
        """
        Parse VCF content.

        Args:
            content: VCF format string

        Yields:
            VariantCall for each variant
        """
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) < 8:
                continue

            chrom, pos, var_id, ref, alt, qual, filt, info = parts[:8]

            # Parse INFO field
            annotations = self._parse_info(info)

            # Parse genotype if present
            genotype = None
            if len(parts) >= 10:
                format_fields = parts[8].split(":")
                sample_values = parts[9].split(":")
                if "GT" in format_fields:
                    gt_idx = format_fields.index("GT")
                    if gt_idx < len(sample_values):
                        genotype = sample_values[gt_idx]

            # Get depth and AF from annotations
            read_depth = annotations.get("DP")
            allele_freq = annotations.get("AF")

            yield VariantCall(
                chrom=chrom,
                pos=int(pos),
                ref=ref,
                alt=alt,
                quality=float(qual) if qual != "." else 0.0,
                filter_status=filt,
                genotype=genotype,
                read_depth=int(read_depth) if read_depth else None,
                allele_frequency=float(allele_freq) if allele_freq else None,
                annotations=annotations,
            )

    def _parse_info(self, info: str) -> dict[str, Any]:
        """Parse VCF INFO field."""
        annotations = {}
        if info == ".":
            return annotations

        for item in info.split(";"):
            if "=" in item:
                key, value = item.split("=", 1)
                # Try to convert to number
                try:
                    if "," in value:
                        annotations[key] = [float(v) for v in value.split(",")]
                    elif "." in value:
                        annotations[key] = float(value)
                    else:
                        annotations[key] = int(value)
                except ValueError:
                    annotations[key] = value
            else:
                annotations[item] = True

        return annotations


class SequenceAnalyzer(BaseBioinfoVerifier):
    """
    Analyze and validate sequences.

    Supports:
    - FASTA/FASTQ parsing
    - Sequence validation
    - Alignment assessment
    - Variant calling verification
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize sequence analyzer."""
        super().__init__(tool_provider)
        self._fasta_parser = FastaParser()
        self._fastq_parser = FastqParser()
        self._vcf_parser = VCFParser()

    @property
    def component_name(self) -> str:
        return "sequence_analyzer"

    async def verify(
        self,
        sequence_data: str,
        format_type: str = "fasta",
    ) -> dict[str, Any]:
        """Verify sequence data."""
        return await self.analyze_sequences(sequence_data, format_type)

    async def analyze_sequences(
        self,
        content: str,
        format_type: str = "fasta",
    ) -> dict[str, Any]:
        """
        Analyze sequences from file content.

        Args:
            content: File content
            format_type: Format type (fasta, fastq, vcf)

        Returns:
            Dict with analysis results
        """
        if format_type == "fasta":
            sequences = list(self._fasta_parser.parse(content))
            return self._summarize_sequences(sequences)
        elif format_type == "fastq":
            reads = list(self._fastq_parser.parse(content))
            return self._summarize_reads(reads)
        elif format_type == "vcf":
            variants = list(self._vcf_parser.parse(content))
            return self._summarize_variants(variants)
        else:
            return {"error": f"Unsupported format: {format_type}"}

    def _summarize_sequences(self, sequences: list[SequenceInfo]) -> dict[str, Any]:
        """Summarize FASTA sequences."""
        if not sequences:
            return {"num_sequences": 0}

        lengths = [s.length for s in sequences]
        gc_contents = [s.gc_content for s in sequences if s.gc_content is not None]

        return {
            "num_sequences": len(sequences),
            "total_length": sum(lengths),
            "min_length": min(lengths),
            "max_length": max(lengths),
            "mean_length": sum(lengths) / len(lengths),
            "sequence_types": list(set(s.sequence_type for s in sequences)),
            "mean_gc_content": sum(gc_contents) / len(gc_contents) if gc_contents else None,
            "sequences": [s.to_dict() for s in sequences[:100]],  # First 100
        }

    def _summarize_reads(self, reads: list[tuple[SequenceInfo, str]]) -> dict[str, Any]:
        """Summarize FASTQ reads."""
        if not reads:
            return {"num_reads": 0}

        sequences = [r[0] for r in reads]
        qualities = [r[1] for r in reads]

        lengths = [s.length for s in sequences]

        # Calculate quality statistics
        mean_qualities = []
        for qual in qualities:
            if qual:
                phred = [ord(c) - 33 for c in qual]
                mean_qualities.append(sum(phred) / len(phred))

        return {
            "num_reads": len(reads),
            "total_bases": sum(lengths),
            "min_length": min(lengths),
            "max_length": max(lengths),
            "mean_length": sum(lengths) / len(lengths),
            "mean_quality": sum(mean_qualities) / len(mean_qualities) if mean_qualities else None,
        }

    def _summarize_variants(self, variants: list[VariantCall]) -> dict[str, Any]:
        """Summarize VCF variants."""
        if not variants:
            return {"num_variants": 0}

        qualities = [v.quality for v in variants if v.quality > 0]

        # Count variant types
        snps = sum(1 for v in variants if len(v.ref) == 1 and len(v.alt) == 1)
        insertions = sum(1 for v in variants if len(v.alt) > len(v.ref))
        deletions = sum(1 for v in variants if len(v.ref) > len(v.alt))

        # Count by filter
        passed = sum(1 for v in variants if v.filter_status == "PASS")

        return {
            "num_variants": len(variants),
            "num_snps": snps,
            "num_insertions": insertions,
            "num_deletions": deletions,
            "num_passed": passed,
            "mean_quality": sum(qualities) / len(qualities) if qualities else None,
            "chromosomes": list(set(v.chrom for v in variants)),
        }

    async def validate_alignment(
        self,
        alignment_file: str,
        reference_file: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate alignment file.

        Args:
            alignment_file: Path to BAM/CRAM file
            reference_file: Path to reference FASTA

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        # Try MCP tool first
        if await self._has_tool("validate_alignment"):
            result = await self._invoke_tool(
                "validate_alignment",
                {
                    "alignment_file": alignment_file,
                    "reference_file": reference_file,
                },
            )
            return result

        # Fall back to samtools
        return await self._validate_with_samtools(alignment_file, reference_file)

    async def _validate_with_samtools(
        self,
        alignment_file: str,
        reference_file: str | None,
    ) -> dict[str, Any]:
        """Validate alignment using samtools."""
        issues = []
        warnings = []
        stats = {}

        # Run samtools quickcheck
        cmd = ["samtools", "quickcheck", alignment_file]
        if settings.use_singularity:
            cmd = [
                "singularity", "exec",
                settings.singularity_image_path,
            ] + cmd

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                issues.append(f"BAM file validation failed: {stderr.decode()}")
                return {"valid": False, "issues": issues}

        except Exception as e:
            issues.append(f"Error running samtools: {str(e)}")
            return {"valid": False, "issues": issues}

        # Run samtools flagstat
        cmd = ["samtools", "flagstat", alignment_file]
        if settings.use_singularity:
            cmd = [
                "singularity", "exec",
                settings.singularity_image_path,
            ] + cmd

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()

            if process.returncode == 0:
                stats = self._parse_flagstat(stdout.decode())

        except Exception as e:
            warnings.append(f"Could not get alignment stats: {str(e)}")

        # Check for common issues
        if stats:
            mapped_pct = stats.get("mapped_pct", 100)
            if mapped_pct < 70:
                warnings.append(f"Low mapping rate: {mapped_pct:.1f}%")

            dup_pct = stats.get("duplicate_pct", 0)
            if dup_pct > 30:
                warnings.append(f"High duplication rate: {dup_pct:.1f}%")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "stats": stats,
        }

    def _parse_flagstat(self, flagstat_output: str) -> dict[str, Any]:
        """Parse samtools flagstat output."""
        stats = {}

        for line in flagstat_output.split("\n"):
            if "in total" in line:
                stats["total_reads"] = int(line.split()[0])
            elif "mapped (" in line:
                parts = line.split()
                stats["mapped_reads"] = int(parts[0])
                # Extract percentage
                pct_match = re.search(r"\(([\d.]+)%", line)
                if pct_match:
                    stats["mapped_pct"] = float(pct_match.group(1))
            elif "duplicates" in line:
                stats["duplicate_reads"] = int(line.split()[0])
            elif "properly paired" in line:
                stats["properly_paired"] = int(line.split()[0])

        # Calculate duplicate percentage
        if "total_reads" in stats and stats["total_reads"] > 0:
            if "duplicate_reads" in stats:
                stats["duplicate_pct"] = (
                    stats["duplicate_reads"] / stats["total_reads"] * 100
                )

        return stats

    async def validate_variants(
        self,
        variants: list[VariantCall],
    ) -> dict[str, Any]:
        """
        Validate variant calls.

        Args:
            variants: List of variant calls

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []
        valid_variants = []
        filtered_variants = []

        for variant in variants:
            variant_issues = []

            # Check quality
            if variant.quality < settings.min_variant_quality:
                variant_issues.append(f"Low quality: {variant.quality}")

            # Check depth
            if variant.read_depth and variant.read_depth < settings.min_read_depth:
                variant_issues.append(f"Low depth: {variant.read_depth}")

            # Check allele frequency
            if variant.allele_frequency is not None:
                if variant.allele_frequency < settings.min_allele_frequency:
                    variant_issues.append(f"Low AF: {variant.allele_frequency}")

            # Check filter status
            if variant.filter_status not in ["PASS", "."]:
                variant_issues.append(f"Filter failed: {variant.filter_status}")

            if variant_issues:
                filtered_variants.append({
                    "variant": variant.to_dict(),
                    "issues": variant_issues,
                })
            else:
                valid_variants.append(variant)

        # Overall statistics
        if not variants:
            warnings.append("No variants to validate")
        elif len(valid_variants) == 0:
            issues.append("All variants failed quality filters")
        elif len(valid_variants) < 0.5 * len(variants):
            warnings.append(
                f"Less than 50% of variants passed filters "
                f"({len(valid_variants)}/{len(variants)})"
            )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "total_variants": len(variants),
            "passed_variants": len(valid_variants),
            "filtered_variants": len(filtered_variants),
        }

    def get_supported_formats(self) -> dict[str, Any]:
        """Get supported sequence formats."""
        return SEQUENCE_FORMATS
