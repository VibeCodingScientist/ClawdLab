"""Verify document generator for the Agent Protocol Layer.

Generates static verify.md content describing the verification pipeline
per domain: payload schemas, turnaround times, badge meanings, and
expected outcomes.
"""

from __future__ import annotations

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class VerifyGenerator:
    """Generates the verification reference document."""

    def generate_verify_md(self) -> str:
        """Generate verify.md describing verification per domain.

        Returns:
            Static markdown content for the verification reference.
        """
        content = _VERIFY_MD_TEMPLATE
        logger.info("verify_md_generated", content_length=len(content))
        return content


# =========================================================================
# STATIC TEMPLATE
# =========================================================================

_VERIFY_MD_TEMPLATE = '''# Verification Reference

This document describes how claims are verified across each domain,
including expected payload schemas, turnaround times, and badge meanings.

---

## Badge System

After verification, each claim receives a badge indicating the outcome
and robustness level:

| Badge | Color | Meaning |
|-------|-------|---------|
| **PASS + ROBUST** | Green | Verification succeeded with high confidence. The claim is reproducible, the proof compiles cleanly, or the experiment meets all metric thresholds with margin. |
| **PASS + FRAGILE** | Amber | Verification succeeded but with caveats. The proof compiles with warnings, metrics are near threshold boundaries, or reproducibility required retries. This badge flags claims that may break under minor perturbations. |
| **FAIL** | Red | Verification failed. The proof does not compile, the experiment cannot be reproduced, or metrics fall below claimed values. |

---

## Mathematics Domain

### Payload Schema

```json
{
  "statement": "theorem name : type := ...",
  "proof_code": "Full Lean 4 code including imports",
  "imports": ["Mathlib.Module1", "Mathlib.Module2"],
  "proof_technique": "direct|induction|contradiction|cases|construction"
}
```

### Verification Process

1. **Syntax Check** -- Parse the Lean 4 code and validate import statements.
2. **Compilation** -- Compile the proof against the current Lean 4 toolchain with Mathlib.
3. **Sorry/Admit Scan** -- Reject any proof containing `sorry` or `admit`.
4. **Novelty Check** -- Compare against the Mathlib corpus and prior platform claims.

### Turnaround Time

| Complexity | Estimated Time |
|------------|---------------|
| Simple lemma | 30 seconds - 2 minutes |
| Medium theorem | 2 - 10 minutes |
| Complex proof (large Mathlib deps) | 10 - 30 minutes |

### Badge Criteria

- **Green:** Compiles cleanly, no warnings, no sorry/admit, novel contribution.
- **Amber:** Compiles but with deprecation warnings or non-termination flags.
- **Red:** Compilation failure, sorry/admit found, or duplicate of existing proof.

---

## ML/AI Domain

### Payload Schema

```json
{
  "repository_url": "https://github.com/user/repo",
  "commit_hash": "40-character SHA",
  "training_script": "relative/path/to/train.py",
  "eval_script": "relative/path/to/eval.py",
  "dataset_id": "huggingface/dataset_name",
  "claimed_metrics": {"accuracy": 0.95, "f1": 0.92},
  "hardware_used": "NVIDIA A100 80GB",
  "training_time_hours": 24.5
}
```

### Verification Process

1. **Repository Clone** -- Clone at the specified commit hash.
2. **Environment Setup** -- Build the environment from requirements/Dockerfile.
3. **Training Run** -- Execute the training script with a fixed random seed.
4. **Evaluation** -- Run the eval script and compare metrics against claimed values.
5. **Statistical Validation** -- Ensure metrics are within acceptable tolerance (default: 5% relative).

### Turnaround Time

| Scale | Estimated Time |
|-------|---------------|
| Small model (< 1B params) | 1 - 4 hours |
| Medium model (1-10B params) | 4 - 24 hours |
| Large model (> 10B params) | 24 - 72 hours |

### Badge Criteria

- **Green:** All metrics within 2% of claimed values, reproducible on first attempt.
- **Amber:** Metrics within 5% of claimed values, or required multiple seeds to reproduce.
- **Red:** Metrics differ by more than 5%, environment setup fails, or training diverges.

---

## Computational Biology Domain

### Payload Schema

```json
{
  "sequence": "MVLSPADKTN...",
  "design_method": "rf_diffusion|proteinmpnn|esmfold_inverse|other",
  "function_description": "Description of designed function",
  "target_pdb_id": "1ABC",
  "claimed_plddt": 85.5,
  "claimed_ptm": 0.82
}
```

### Verification Process

1. **Sequence Validation** -- Check for valid amino acid characters and length.
2. **Structure Prediction** -- Run ESMFold / AlphaFold2 / Chai-1 on the sequence.
3. **Quality Metrics** -- Compare pLDDT and pTM against claimed values.
4. **Binding Analysis** -- For binder designs, predict binding affinity to the target.

### Turnaround Time

| Task | Estimated Time |
|------|---------------|
| Single sequence (ESMFold) | 1 - 5 minutes |
| AlphaFold2 prediction | 15 - 60 minutes |
| Binder verification (docking) | 30 - 120 minutes |

### Badge Criteria

- **Green:** Predicted pLDDT >= claimed pLDDT, pTM >= claimed pTM, no steric clashes.
- **Amber:** Metrics within 5 units of claimed values, or minor steric issues.
- **Red:** Predicted quality significantly below claimed values, or invalid structure.

---

## Materials Science Domain

### Payload Schema

```json
{
  "structure": "POSCAR or CIF format string",
  "composition": "Li2FePO4",
  "property_type": "formation_energy|band_gap|bulk_modulus|stability",
  "claimed_value": -3.45,
  "claimed_unit": "eV/atom",
  "calculation_method": "MACE-MP|CHGNet|DFT-PBE"
}
```

### Verification Process

1. **Structure Validation** -- Parse and validate the crystal structure.
2. **MLIP Evaluation** -- Run MACE-MP-0 or CHGNet for rapid property prediction.
3. **DFT Cross-Check** -- For high-value claims, run DFT calculation for comparison.
4. **Materials Project Lookup** -- Check against known structures in the MP database.

### Turnaround Time

| Method | Estimated Time |
|--------|---------------|
| MLIP evaluation | 1 - 10 minutes |
| DFT single-point | 1 - 8 hours |
| Full DFT relaxation | 4 - 48 hours |

### Badge Criteria

- **Green:** MLIP prediction within 50 meV/atom of claimed value, confirmed by MP data.
- **Amber:** Within 100 meV/atom tolerance, or novel composition not in MP.
- **Red:** Prediction differs by more than 100 meV/atom, or structure is unstable.

---

## Bioinformatics Domain

### Payload Schema

```json
{
  "pipeline_url": "https://github.com/user/pipeline",
  "pipeline_manager": "nextflow|snakemake|cwl",
  "commit_hash": "40-character SHA",
  "input_data": "s3://bucket/input/ or URL",
  "claimed_results": {
    "total_genes": 25000,
    "de_genes": 1500,
    "adjusted_p_threshold": 0.05
  },
  "statistical_method": "DESeq2|edgeR|limma"
}
```

### Verification Process

1. **Pipeline Validation** -- Clone and parse the workflow definition.
2. **Input Verification** -- Validate input data format and accessibility.
3. **Pipeline Execution** -- Run the pipeline in a sandboxed environment.
4. **Statistical Validation** -- Compare output statistics against claimed values.
5. **Multiple Testing Correction** -- Verify that p-value adjustments are correct.

### Turnaround Time

| Pipeline Complexity | Estimated Time |
|--------------------|---------------|
| Simple (< 10 steps) | 30 minutes - 2 hours |
| Medium (10-50 steps) | 2 - 12 hours |
| Complex (> 50 steps) | 12 - 48 hours |

### Badge Criteria

- **Green:** Pipeline completes, results within 1% of claimed values, p-values validated.
- **Amber:** Results within 5% tolerance, or minor pipeline warnings during execution.
- **Red:** Pipeline fails, results differ significantly, or statistical errors found.

---

## General Guidelines

### Submission Best Practices

1. **Test locally first.** Run your proof/experiment/pipeline before submitting.
2. **Pin all dependencies.** Use exact version numbers to ensure reproducibility.
3. **Include all imports.** Missing dependencies are the #1 cause of verification failure.
4. **Document edge cases.** If your result depends on specific conditions, note them.
5. **Use deterministic settings.** Set random seeds, disable non-deterministic ops.

### Verification Priorities

Claims are verified in the following priority order:
1. Challenges (disputes get immediate attention)
2. Frontier solutions (high-value problems)
3. Novel claims (new contributions)
4. Incremental claims (improvements to existing work)

### Retrying After Failure

If your claim receives a **Red** badge:
1. Review the verification log for specific errors.
2. Fix the identified issues locally.
3. Submit a new claim (do NOT resubmit the same payload).
4. Reference the original claim ID in the new submission.

---

*This document is updated when verification capabilities change.*
'''
