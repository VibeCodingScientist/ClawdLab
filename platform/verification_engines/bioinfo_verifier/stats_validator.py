"""Statistical validation service for bioinformatics claims."""

import math
from typing import Any

from platform.verification_engines.bioinfo_verifier.base import (
    BaseBioinfoVerifier,
    MCPToolProvider,
    MultipleTestingCorrection,
    StatisticalSignificance,
    StatisticalTest,
    StatisticalValidation,
)
from platform.verification_engines.bioinfo_verifier.config import (
    STATISTICAL_METHODS,
    get_settings,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class StatisticalValidator(BaseBioinfoVerifier):
    """
    Validate statistical claims in bioinformatics analyses.

    Checks:
    - P-value validity
    - Effect size appropriateness
    - Multiple testing corrections
    - Sample size adequacy
    - Power analysis
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize statistical validator."""
        super().__init__(tool_provider)

    @property
    def component_name(self) -> str:
        return "stats_validator"

    async def verify(
        self,
        claim: dict[str, Any],
    ) -> StatisticalValidation:
        """Validate a statistical claim."""
        return await self.validate_statistical_claim(claim)

    async def validate_statistical_claim(
        self,
        claim: dict[str, Any],
    ) -> StatisticalValidation:
        """
        Validate a statistical claim.

        Args:
            claim: Dict containing:
                - test_type: Type of statistical test
                - pvalue: Reported p-value
                - test_statistic: Test statistic value
                - effect_size: Effect size (optional)
                - sample_sizes: Sample sizes per group

        Returns:
            StatisticalValidation with validation results
        """
        issues = []
        warnings = []
        tests = []

        test_type = claim.get("test_type", "")
        pvalue = claim.get("pvalue")
        test_statistic = claim.get("test_statistic")
        effect_size = claim.get("effect_size")
        sample_sizes = claim.get("sample_sizes", [])

        # Validate p-value
        if pvalue is not None:
            pvalue_valid, pvalue_issues = self._validate_pvalue(pvalue)
            if not pvalue_valid:
                issues.extend(pvalue_issues)

        # Validate test statistic
        if test_statistic is not None and test_type:
            stat_valid, stat_issues = self._validate_test_statistic(
                test_type, test_statistic, pvalue, sample_sizes
            )
            if not stat_valid:
                issues.extend(stat_issues)

        # Validate effect size
        if effect_size is not None:
            effect_valid, effect_warnings = self._validate_effect_size(effect_size, test_type)
            if not effect_valid:
                warnings.extend(effect_warnings)

        # Check sample size adequacy
        sample_adequate = True
        if sample_sizes:
            sample_adequate, sample_warnings = self._check_sample_size(sample_sizes, effect_size)
            warnings.extend(sample_warnings)

        # Calculate power if possible
        power = None
        if sample_sizes and effect_size and pvalue:
            power = self._estimate_power(sample_sizes, effect_size, pvalue)
            if power and power < 0.8:
                warnings.append(f"Low statistical power: {power:.2f}")

        # Create test record
        if pvalue is not None:
            tests.append(StatisticalTest(
                test_name=test_type,
                test_statistic=test_statistic or 0.0,
                pvalue=pvalue,
                effect_size=effect_size,
                sample_sizes=sample_sizes,
                method=test_type,
            ))

        # Determine significance
        if pvalue is not None:
            if pvalue < settings.pvalue_threshold:
                significance = StatisticalSignificance.SIGNIFICANT
            elif pvalue < 0.1:
                significance = StatisticalSignificance.MARGINAL
            else:
                significance = StatisticalSignificance.NOT_SIGNIFICANT
        else:
            significance = StatisticalSignificance.NOT_SIGNIFICANT

        if power and power < 0.5:
            significance = StatisticalSignificance.UNDERPOWERED

        return StatisticalValidation(
            valid=len(issues) == 0,
            significance=significance,
            tests=tests,
            issues=issues,
            warnings=warnings,
            power=power,
            sample_size_adequate=sample_adequate,
        )

    def _validate_pvalue(self, pvalue: float) -> tuple[bool, list[str]]:
        """Validate p-value is reasonable."""
        issues = []

        if pvalue < 0:
            issues.append(f"Invalid p-value: {pvalue} (cannot be negative)")
        elif pvalue > 1:
            issues.append(f"Invalid p-value: {pvalue} (cannot exceed 1)")
        elif pvalue == 0:
            issues.append("P-value of exactly 0 is unrealistic; should report as < threshold")
        elif pvalue < 1e-300:
            issues.append(f"P-value {pvalue} is unrealistically small; possible numerical error")

        return len(issues) == 0, issues

    def _validate_test_statistic(
        self,
        test_type: str,
        statistic: float,
        pvalue: float | None,
        sample_sizes: list[int],
    ) -> tuple[bool, list[str]]:
        """Validate test statistic is consistent with p-value."""
        issues = []

        # Basic sanity checks
        if test_type in ["t-test", "t_test"]:
            # t-statistic should be finite
            if not math.isfinite(statistic):
                issues.append(f"Invalid t-statistic: {statistic}")

            # Check consistency with p-value (rough check)
            if pvalue is not None and len(sample_sizes) >= 2:
                df = sum(sample_sizes) - 2
                if df > 0:
                    expected_significant = abs(statistic) > 2  # rough threshold
                    is_significant = pvalue < 0.05
                    if expected_significant != is_significant and abs(statistic - 2) > 0.5:
                        issues.append(
                            f"Inconsistent t-statistic ({statistic}) and p-value ({pvalue})"
                        )

        elif test_type in ["chi-square", "chi_square", "chisq"]:
            if statistic < 0:
                issues.append(f"Chi-square statistic cannot be negative: {statistic}")

        elif test_type in ["f-test", "f_test", "anova"]:
            if statistic < 0:
                issues.append(f"F-statistic cannot be negative: {statistic}")

        elif test_type in ["wilcoxon", "mann-whitney", "mann_whitney"]:
            if statistic < 0:
                issues.append(f"Rank statistic cannot be negative: {statistic}")

        return len(issues) == 0, issues

    def _validate_effect_size(
        self,
        effect_size: float,
        test_type: str,
    ) -> tuple[bool, list[str]]:
        """Validate effect size is reasonable."""
        warnings = []

        # For log2 fold changes
        if test_type in ["de", "differential_expression", "fold_change"]:
            if abs(effect_size) < settings.min_effect_size:
                warnings.append(
                    f"Small effect size: |log2FC| = {abs(effect_size):.2f} < {settings.min_effect_size}"
                )

        # For Cohen's d
        elif test_type in ["t-test", "t_test"]:
            if abs(effect_size) < 0.2:
                warnings.append(f"Small effect size (Cohen's d = {effect_size:.2f})")
            elif abs(effect_size) > 3:
                warnings.append(f"Unusually large effect size (Cohen's d = {effect_size:.2f})")

        # For correlation
        elif test_type in ["correlation", "pearson", "spearman"]:
            if abs(effect_size) > 1:
                warnings.append(f"Invalid correlation: {effect_size}")
            elif abs(effect_size) < 0.1:
                warnings.append(f"Weak correlation: r = {effect_size:.2f}")

        return True, warnings  # Effect size issues are warnings, not errors

    def _check_sample_size(
        self,
        sample_sizes: list[int],
        effect_size: float | None,
    ) -> tuple[bool, list[str]]:
        """Check sample size adequacy."""
        warnings = []

        # Check minimum per group
        for i, n in enumerate(sample_sizes):
            if n < settings.min_samples_per_group:
                warnings.append(
                    f"Group {i+1} has only {n} samples (minimum: {settings.min_samples_per_group})"
                )

        # Check for imbalanced groups
        if len(sample_sizes) >= 2:
            min_n = min(sample_sizes)
            max_n = max(sample_sizes)
            if max_n > 3 * min_n:
                warnings.append(
                    f"Highly imbalanced groups: {sample_sizes} (ratio > 3:1)"
                )

        # Very small total sample
        total_n = sum(sample_sizes)
        if total_n < 10:
            warnings.append(f"Very small total sample size: n = {total_n}")

        adequate = all(n >= settings.min_samples_per_group for n in sample_sizes)
        return adequate, warnings

    def _estimate_power(
        self,
        sample_sizes: list[int],
        effect_size: float,
        pvalue: float,
    ) -> float | None:
        """Estimate statistical power (simplified)."""
        if len(sample_sizes) < 2:
            return None

        n1, n2 = sample_sizes[0], sample_sizes[1] if len(sample_sizes) > 1 else sample_sizes[0]
        total_n = n1 + n2

        # Simplified power estimation using normal approximation
        # Power ≈ Φ(|effect| * sqrt(n/2) - z_α/2)
        z_alpha = 1.96  # Two-sided α = 0.05

        if effect_size == 0:
            return 0.05  # Type I error rate

        # Effective sample size for unequal groups
        n_eff = (2 * n1 * n2) / (n1 + n2) if n1 > 0 and n2 > 0 else 0

        if n_eff == 0:
            return None

        ncp = abs(effect_size) * math.sqrt(n_eff / 2)  # Non-centrality parameter

        # Normal approximation to power
        z = ncp - z_alpha

        # Approximate CDF of standard normal
        power = 0.5 * (1 + math.erf(z / math.sqrt(2)))

        return max(0.0, min(1.0, power))

    async def apply_multiple_testing_correction(
        self,
        pvalues: list[float],
        method: str = "bh",
        alpha: float = 0.05,
    ) -> MultipleTestingCorrection:
        """
        Apply multiple testing correction.

        Args:
            pvalues: List of p-values
            method: Correction method (bonferroni, bh, by, holm)
            alpha: Significance threshold

        Returns:
            MultipleTestingCorrection with adjusted p-values
        """
        n = len(pvalues)
        if n == 0:
            return MultipleTestingCorrection(
                method=method,
                original_pvalues=[],
                adjusted_pvalues=[],
                alpha=alpha,
                num_significant=0,
            )

        if method == "bonferroni":
            adjusted = [min(1.0, p * n) for p in pvalues]

        elif method == "bh":  # Benjamini-Hochberg
            adjusted = self._bh_correction(pvalues)

        elif method == "by":  # Benjamini-Yekutieli
            adjusted = self._by_correction(pvalues)

        elif method == "holm":
            adjusted = self._holm_correction(pvalues)

        else:
            # Default to Bonferroni
            adjusted = [min(1.0, p * n) for p in pvalues]

        num_significant = sum(1 for p in adjusted if p < alpha)

        return MultipleTestingCorrection(
            method=method,
            original_pvalues=pvalues,
            adjusted_pvalues=adjusted,
            alpha=alpha,
            num_significant=num_significant,
        )

    def _bh_correction(self, pvalues: list[float]) -> list[float]:
        """Benjamini-Hochberg correction."""
        n = len(pvalues)
        indexed = sorted(enumerate(pvalues), key=lambda x: x[1])

        adjusted = [0.0] * n
        cummin = 1.0

        for i in range(n - 1, -1, -1):
            idx, p = indexed[i]
            adjusted_p = min(cummin, p * n / (i + 1))
            adjusted_p = min(1.0, adjusted_p)
            cummin = min(cummin, adjusted_p)
            adjusted[idx] = adjusted_p

        return adjusted

    def _by_correction(self, pvalues: list[float]) -> list[float]:
        """Benjamini-Yekutieli correction."""
        n = len(pvalues)
        c_n = sum(1.0 / i for i in range(1, n + 1))  # Harmonic sum

        indexed = sorted(enumerate(pvalues), key=lambda x: x[1])
        adjusted = [0.0] * n
        cummin = 1.0

        for i in range(n - 1, -1, -1):
            idx, p = indexed[i]
            adjusted_p = min(cummin, p * n * c_n / (i + 1))
            adjusted_p = min(1.0, adjusted_p)
            cummin = min(cummin, adjusted_p)
            adjusted[idx] = adjusted_p

        return adjusted

    def _holm_correction(self, pvalues: list[float]) -> list[float]:
        """Holm-Bonferroni correction."""
        n = len(pvalues)
        indexed = sorted(enumerate(pvalues), key=lambda x: x[1])

        adjusted = [0.0] * n
        cummax = 0.0

        for i, (idx, p) in enumerate(indexed):
            adjusted_p = max(cummax, p * (n - i))
            adjusted_p = min(1.0, adjusted_p)
            cummax = max(cummax, adjusted_p)
            adjusted[idx] = adjusted_p

        return adjusted

    async def validate_de_statistics(
        self,
        genes: list[dict[str, Any]],
        method: str = "deseq2",
    ) -> dict[str, Any]:
        """
        Validate differential expression statistics.

        Args:
            genes: List of gene results with pvalue, log2FC, etc.
            method: DE method used (deseq2, edger, limma)

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        pvalues = [g.get("pvalue", 1.0) for g in genes if g.get("pvalue") is not None]
        adj_pvalues = [g.get("adjusted_pvalue", g.get("padj", 1.0)) for g in genes]
        log2fcs = [g.get("log2_fold_change", g.get("log2FoldChange", 0)) for g in genes]

        # Check p-value distribution
        if pvalues:
            # P-values should be uniformly distributed under null
            uniform_pvalues = [p for p in pvalues if p > 0.5]
            if len(uniform_pvalues) < 0.3 * len(pvalues):
                warnings.append("Unusual p-value distribution; check for batch effects")

            # Check for suspicious clustering
            very_small = sum(1 for p in pvalues if p < 1e-10) / len(pvalues)
            if very_small > 0.1:
                warnings.append(f"{very_small*100:.1f}% of p-values < 1e-10; check normalization")

        # Validate adjusted p-values
        if adj_pvalues and pvalues:
            # Adjusted should be >= original
            for i, (p, adj) in enumerate(zip(pvalues, adj_pvalues)):
                if adj < p and p > 0:
                    issues.append(f"Gene {i}: adjusted p-value ({adj}) < raw p-value ({p})")

        # Check fold changes
        if log2fcs:
            extreme_fc = sum(1 for fc in log2fcs if abs(fc) > 10)
            if extreme_fc > 0:
                warnings.append(f"{extreme_fc} genes with |log2FC| > 10; check for artifacts")

        # Method-specific checks
        if method == "deseq2":
            # DESeq2 uses shrunken estimates
            lfcse = [g.get("lfcSE") for g in genes if g.get("lfcSE") is not None]
            if lfcse:
                if any(se <= 0 for se in lfcse):
                    issues.append("DESeq2 reported non-positive standard errors")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "num_genes": len(genes),
            "num_significant": sum(1 for p in adj_pvalues if p < settings.fdr_threshold),
        }

    def get_supported_methods(self) -> list[dict[str, Any]]:
        """Get list of supported statistical methods."""
        return [
            {
                "id": method_id,
                "name": config["name"],
                "description": config["description"],
            }
            for method_id, config in STATISTICAL_METHODS.items()
        ]
