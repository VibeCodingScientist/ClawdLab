"""Differential expression validation service."""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from platform.verification_engines.bioinfo_verifier.base import (
    BaseBioinfoVerifier,
    DEGene,
    DEResult,
    EnrichmentTerm,
    MCPToolProvider,
)
from platform.verification_engines.bioinfo_verifier.config import get_settings
from platform.verification_engines.bioinfo_verifier.stats_validator import (
    StatisticalValidator,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DEValidator(BaseBioinfoVerifier):
    """
    Validate differential expression analysis results.

    Supports:
    - DESeq2 result validation
    - edgeR result validation
    - limma-voom result validation
    - Re-running analysis for verification
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize DE validator."""
        super().__init__(tool_provider)
        self._stats_validator = StatisticalValidator(tool_provider)

    @property
    def component_name(self) -> str:
        return "de_validator"

    async def verify(
        self,
        de_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify differential expression result."""
        return await self.validate_de_result(de_result)

    async def validate_de_result(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate a differential expression result.

        Args:
            result: DE result dict containing:
                - genes: List of gene results
                - method: DE method used
                - contrast: Comparison made

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        genes = result.get("genes", [])
        method = result.get("method", "deseq2")
        contrast = result.get("contrast", "")

        if not genes:
            issues.append("No genes in result")
            return {"valid": False, "issues": issues}

        # Validate individual genes
        parsed_genes = []
        for gene_data in genes:
            gene = DEGene(
                gene_id=gene_data.get("gene_id", gene_data.get("ensembl_id", "")),
                gene_name=gene_data.get("gene_name", gene_data.get("symbol")),
                log2_fold_change=gene_data.get("log2_fold_change", gene_data.get("log2FoldChange", 0.0)),
                pvalue=gene_data.get("pvalue", gene_data.get("pval", 1.0)),
                adjusted_pvalue=gene_data.get("adjusted_pvalue", gene_data.get("padj", 1.0)),
                base_mean=gene_data.get("base_mean", gene_data.get("baseMean", 0.0)),
                lfcse=gene_data.get("lfcSE"),
            )
            parsed_genes.append(gene)

        # Validate statistics
        stats_validation = await self._stats_validator.validate_de_statistics(
            [g.__dict__ for g in parsed_genes],
            method=method,
        )
        issues.extend(stats_validation.get("issues", []))
        warnings.extend(stats_validation.get("warnings", []))

        # Check for minimum counts filtering
        if all(g.base_mean < settings.min_counts_per_gene for g in parsed_genes):
            issues.append("All genes have very low counts; check filtering")

        # Count significant genes
        significant = [g for g in parsed_genes if g.is_significant]
        up_regulated = [g for g in significant if g.log2_fold_change > 0]
        down_regulated = [g for g in significant if g.log2_fold_change < 0]

        # Check for highly imbalanced results
        if significant:
            up_pct = len(up_regulated) / len(significant)
            if up_pct > 0.9 or up_pct < 0.1:
                warnings.append(
                    f"Highly imbalanced DE: {len(up_regulated)} up, {len(down_regulated)} down"
                )

        # Build DE result
        de_result = DEResult(
            method=method,
            contrast=contrast,
            genes=parsed_genes,
            num_tested=len(parsed_genes),
            num_significant=len(significant),
            num_up=len(up_regulated),
            num_down=len(down_regulated),
        )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "result": de_result.to_dict(),
        }

    async def reproduce_de_analysis(
        self,
        counts_file: str,
        sample_info: dict[str, str],
        design: str,
        contrast: str,
        method: str = "deseq2",
    ) -> DEResult | None:
        """
        Reproduce differential expression analysis.

        Args:
            counts_file: Path to counts matrix
            sample_info: Sample -> group mapping
            design: Design formula
            contrast: Contrast to test
            method: DE method (deseq2, edger, limma)

        Returns:
            DEResult or None if failed
        """
        # Try MCP tool first
        if await self._has_tool(f"{method}_analysis"):
            result = await self._invoke_tool(
                f"{method}_analysis",
                {
                    "counts_file": counts_file,
                    "sample_info": sample_info,
                    "design": design,
                    "contrast": contrast,
                },
            )
            return self._parse_de_result(result, method, contrast)

        # Fall back to local execution
        if method == "deseq2":
            return await self._run_deseq2(counts_file, sample_info, design, contrast)
        elif method == "edger":
            return await self._run_edger(counts_file, sample_info, design, contrast)
        elif method == "limma":
            return await self._run_limma(counts_file, sample_info, design, contrast)

        return None

    async def _run_deseq2(
        self,
        counts_file: str,
        sample_info: dict[str, str],
        design: str,
        contrast: str,
    ) -> DEResult | None:
        """Run DESeq2 analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sample info file
            sample_file = Path(tmpdir) / "samples.tsv"
            with open(sample_file, "w") as f:
                f.write("sample\tcondition\n")
                for sample, condition in sample_info.items():
                    f.write(f"{sample}\t{condition}\n")

            # Create R script
            r_script = f"""
library(DESeq2)

# Load data
counts <- read.table("{counts_file}", header=TRUE, row.names=1, sep="\\t")
coldata <- read.table("{sample_file}", header=TRUE, row.names=1, sep="\\t")

# Ensure matching samples
coldata <- coldata[colnames(counts),,drop=FALSE]

# Create DESeq2 object
dds <- DESeqDataSetFromMatrix(
    countData = counts,
    colData = coldata,
    design = {design}
)

# Filter low counts
keep <- rowSums(counts(dds)) >= {settings.min_counts_per_gene}
dds <- dds[keep,]

# Run DESeq2
dds <- DESeq(dds)

# Get results
res <- results(dds, name="{contrast}")
res_df <- as.data.frame(res)
res_df$gene_id <- rownames(res_df)

# Output
write.table(res_df, "{tmpdir}/results.tsv", sep="\\t", quote=FALSE, row.names=FALSE)
"""
            script_path = Path(tmpdir) / "deseq2.R"
            script_path.write_text(r_script)

            # Run R script
            if settings.use_singularity:
                cmd = [
                    "singularity", "exec",
                    settings.singularity_image_path,
                    "Rscript", str(script_path),
                ]
            else:
                cmd = ["Rscript", str(script_path)]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.pipeline_timeout,
                )

                if process.returncode != 0:
                    logger.warning("deseq2_failed", error=stderr.decode())
                    return None

                # Parse results
                results_file = Path(tmpdir) / "results.tsv"
                if results_file.exists():
                    return self._parse_deseq2_results(results_file.read_text(), contrast)

            except Exception as e:
                logger.warning("deseq2_error", error=str(e))

        return None

    async def _run_edger(
        self,
        counts_file: str,
        sample_info: dict[str, str],
        design: str,
        contrast: str,
    ) -> DEResult | None:
        """Run edgeR analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_file = Path(tmpdir) / "samples.tsv"
            with open(sample_file, "w") as f:
                f.write("sample\tcondition\n")
                for sample, condition in sample_info.items():
                    f.write(f"{sample}\t{condition}\n")

            r_script = f"""
library(edgeR)

# Load data
counts <- read.table("{counts_file}", header=TRUE, row.names=1, sep="\\t")
coldata <- read.table("{sample_file}", header=TRUE, row.names=1, sep="\\t")
coldata <- coldata[colnames(counts),,drop=FALSE]

# Create DGEList
y <- DGEList(counts=counts, group=coldata$condition)

# Filter
keep <- filterByExpr(y)
y <- y[keep,,keep.lib.sizes=FALSE]

# Normalize
y <- calcNormFactors(y, method="TMM")

# Design matrix
design <- model.matrix(~condition, data=coldata)

# Estimate dispersion
y <- estimateDisp(y, design)

# Fit model
fit <- glmQLFit(y, design)
qlf <- glmQLFTest(fit, coef=2)

# Get results
res <- topTags(qlf, n=Inf)$table
res$gene_id <- rownames(res)

write.table(res, "{tmpdir}/results.tsv", sep="\\t", quote=FALSE, row.names=FALSE)
"""
            script_path = Path(tmpdir) / "edger.R"
            script_path.write_text(r_script)

            if settings.use_singularity:
                cmd = [
                    "singularity", "exec",
                    settings.singularity_image_path,
                    "Rscript", str(script_path),
                ]
            else:
                cmd = ["Rscript", str(script_path)]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.pipeline_timeout,
                )

                if process.returncode != 0:
                    logger.warning("edger_failed", error=stderr.decode())
                    return None

                results_file = Path(tmpdir) / "results.tsv"
                if results_file.exists():
                    return self._parse_edger_results(results_file.read_text(), contrast)

            except Exception as e:
                logger.warning("edger_error", error=str(e))

        return None

    async def _run_limma(
        self,
        counts_file: str,
        sample_info: dict[str, str],
        design: str,
        contrast: str,
    ) -> DEResult | None:
        """Run limma-voom analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_file = Path(tmpdir) / "samples.tsv"
            with open(sample_file, "w") as f:
                f.write("sample\tcondition\n")
                for sample, condition in sample_info.items():
                    f.write(f"{sample}\t{condition}\n")

            r_script = f"""
library(limma)
library(edgeR)

# Load data
counts <- read.table("{counts_file}", header=TRUE, row.names=1, sep="\\t")
coldata <- read.table("{sample_file}", header=TRUE, row.names=1, sep="\\t")
coldata <- coldata[colnames(counts),,drop=FALSE]

# Create DGEList
dge <- DGEList(counts=counts)

# Filter
keep <- filterByExpr(dge)
dge <- dge[keep,,keep.lib.sizes=FALSE]

# Normalize
dge <- calcNormFactors(dge)

# Design
design <- model.matrix(~condition, data=coldata)

# voom
v <- voom(dge, design, plot=FALSE)

# Fit
fit <- lmFit(v, design)
fit <- eBayes(fit)

# Results
res <- topTable(fit, coef=2, n=Inf)
res$gene_id <- rownames(res)

write.table(res, "{tmpdir}/results.tsv", sep="\\t", quote=FALSE, row.names=FALSE)
"""
            script_path = Path(tmpdir) / "limma.R"
            script_path.write_text(r_script)

            if settings.use_singularity:
                cmd = [
                    "singularity", "exec",
                    settings.singularity_image_path,
                    "Rscript", str(script_path),
                ]
            else:
                cmd = ["Rscript", str(script_path)]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.pipeline_timeout,
                )

                if process.returncode != 0:
                    logger.warning("limma_failed", error=stderr.decode())
                    return None

                results_file = Path(tmpdir) / "results.tsv"
                if results_file.exists():
                    return self._parse_limma_results(results_file.read_text(), contrast)

            except Exception as e:
                logger.warning("limma_error", error=str(e))

        return None

    def _parse_deseq2_results(self, content: str, contrast: str) -> DEResult:
        """Parse DESeq2 results."""
        genes = []
        lines = content.strip().split("\n")
        header = lines[0].split("\t")

        for line in lines[1:]:
            values = line.split("\t")
            if len(values) < len(header):
                continue

            row = dict(zip(header, values))

            try:
                gene = DEGene(
                    gene_id=row.get("gene_id", ""),
                    log2_fold_change=float(row.get("log2FoldChange", 0)),
                    pvalue=float(row.get("pvalue", 1)) if row.get("pvalue", "NA") != "NA" else 1.0,
                    adjusted_pvalue=float(row.get("padj", 1)) if row.get("padj", "NA") != "NA" else 1.0,
                    base_mean=float(row.get("baseMean", 0)),
                    lfcse=float(row.get("lfcSE", 0)) if row.get("lfcSE", "NA") != "NA" else None,
                )
                genes.append(gene)
            except (ValueError, KeyError):
                continue

        significant = [g for g in genes if g.is_significant]

        return DEResult(
            method="deseq2",
            contrast=contrast,
            genes=genes,
            num_tested=len(genes),
            num_significant=len(significant),
            num_up=len([g for g in significant if g.log2_fold_change > 0]),
            num_down=len([g for g in significant if g.log2_fold_change < 0]),
        )

    def _parse_edger_results(self, content: str, contrast: str) -> DEResult:
        """Parse edgeR results."""
        genes = []
        lines = content.strip().split("\n")
        header = lines[0].split("\t")

        for line in lines[1:]:
            values = line.split("\t")
            if len(values) < len(header):
                continue

            row = dict(zip(header, values))

            try:
                gene = DEGene(
                    gene_id=row.get("gene_id", ""),
                    log2_fold_change=float(row.get("logFC", 0)),
                    pvalue=float(row.get("PValue", 1)),
                    adjusted_pvalue=float(row.get("FDR", 1)),
                    base_mean=float(row.get("logCPM", 0)),
                )
                genes.append(gene)
            except (ValueError, KeyError):
                continue

        significant = [g for g in genes if g.is_significant]

        return DEResult(
            method="edger",
            contrast=contrast,
            genes=genes,
            num_tested=len(genes),
            num_significant=len(significant),
            num_up=len([g for g in significant if g.log2_fold_change > 0]),
            num_down=len([g for g in significant if g.log2_fold_change < 0]),
        )

    def _parse_limma_results(self, content: str, contrast: str) -> DEResult:
        """Parse limma results."""
        genes = []
        lines = content.strip().split("\n")
        header = lines[0].split("\t")

        for line in lines[1:]:
            values = line.split("\t")
            if len(values) < len(header):
                continue

            row = dict(zip(header, values))

            try:
                gene = DEGene(
                    gene_id=row.get("gene_id", ""),
                    log2_fold_change=float(row.get("logFC", 0)),
                    pvalue=float(row.get("P.Value", 1)),
                    adjusted_pvalue=float(row.get("adj.P.Val", 1)),
                    base_mean=float(row.get("AveExpr", 0)),
                )
                genes.append(gene)
            except (ValueError, KeyError):
                continue

        significant = [g for g in genes if g.is_significant]

        return DEResult(
            method="limma",
            contrast=contrast,
            genes=genes,
            num_tested=len(genes),
            num_significant=len(significant),
            num_up=len([g for g in significant if g.log2_fold_change > 0]),
            num_down=len([g for g in significant if g.log2_fold_change < 0]),
        )

    def _parse_de_result(
        self,
        result: dict[str, Any],
        method: str,
        contrast: str,
    ) -> DEResult:
        """Parse MCP tool DE result."""
        genes = [
            DEGene(
                gene_id=g.get("gene_id", ""),
                gene_name=g.get("gene_name"),
                log2_fold_change=g.get("log2_fold_change", 0),
                pvalue=g.get("pvalue", 1),
                adjusted_pvalue=g.get("adjusted_pvalue", 1),
                base_mean=g.get("base_mean", 0),
            )
            for g in result.get("genes", [])
        ]

        significant = [g for g in genes if g.is_significant]

        return DEResult(
            method=method,
            contrast=contrast,
            genes=genes,
            num_tested=len(genes),
            num_significant=len(significant),
            num_up=len([g for g in significant if g.log2_fold_change > 0]),
            num_down=len([g for g in significant if g.log2_fold_change < 0]),
        )

    async def compare_de_results(
        self,
        result1: DEResult,
        result2: DEResult,
        threshold: float = 0.9,
    ) -> dict[str, Any]:
        """
        Compare two DE results for concordance.

        Args:
            result1: First DE result
            result2: Second DE result
            threshold: Minimum concordance threshold

        Returns:
            Dict with comparison metrics
        """
        genes1 = {g.gene_id: g for g in result1.genes}
        genes2 = {g.gene_id: g for g in result2.genes}

        common_genes = set(genes1.keys()) & set(genes2.keys())

        if not common_genes:
            return {
                "concordant": False,
                "common_genes": 0,
                "error": "No common genes",
            }

        # Compare significance calls
        concordant_sig = 0
        concordant_dir = 0

        for gene_id in common_genes:
            g1 = genes1[gene_id]
            g2 = genes2[gene_id]

            # Same significance
            if g1.is_significant == g2.is_significant:
                concordant_sig += 1

            # Same direction (for significant)
            if g1.is_significant and g2.is_significant:
                if (g1.log2_fold_change > 0) == (g2.log2_fold_change > 0):
                    concordant_dir += 1

        sig_concordance = concordant_sig / len(common_genes)
        sig1 = len([g for g in result1.genes if g.is_significant])
        sig2 = len([g for g in result2.genes if g.is_significant])

        dir_concordance = (
            concordant_dir / min(sig1, sig2) if min(sig1, sig2) > 0 else 1.0
        )

        return {
            "concordant": sig_concordance >= threshold,
            "common_genes": len(common_genes),
            "significance_concordance": sig_concordance,
            "direction_concordance": dir_concordance,
            "result1_significant": sig1,
            "result2_significant": sig2,
        }
