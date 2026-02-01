"""Tests for claim payload validation integration."""

import pytest
from platform.shared.schemas.claim_payloads import validate_payload, get_payload_schema


class TestPayloadValidation:
    """Tests for validate_payload function."""

    def test_valid_math_theorem_passes(self):
        """Valid mathematics theorem payload should pass validation."""
        payload = {
            "statement": "theorem foo : Nat → Nat → Prop := by exact fun n m => n = m",
            "proof_code": "theorem foo : True := by trivial\n-- complete proof with declaration",
            "imports": ["Mathlib.Tactic.Ring"],
            "proof_technique": "direct",
        }
        result = validate_payload("mathematics", "theorem", payload)
        assert "statement" in result
        assert "proof_code" in result

    def test_sorry_in_proof_rejected(self):
        """Proofs containing 'sorry' should be rejected."""
        payload = {
            "statement": "theorem foo : Nat → Nat → Prop := by exact fun n m => n = m",
            "proof_code": "theorem foo : True := by sorry\n-- incomplete proof",
            "imports": [],
            "proof_technique": "direct",
        }
        with pytest.raises(ValueError, match="sorry"):
            validate_payload("mathematics", "theorem", payload)

    def test_admit_in_proof_rejected(self):
        """Proofs containing 'admit' should be rejected."""
        payload = {
            "statement": "theorem foo : Nat → Nat → Prop := by exact fun n m => n = m",
            "proof_code": "theorem foo : True := by admit\n-- admitted proof",
            "imports": [],
            "proof_technique": "direct",
        }
        with pytest.raises(ValueError, match="admit"):
            validate_payload("mathematics", "theorem", payload)

    def test_invalid_amino_acids_rejected(self):
        """Protein sequences with invalid characters should be rejected."""
        payload = {
            "sequence": "ACDEFGHIKLMNPQRSTVWY123",  # 123 are invalid
            "design_method": "rf_diffusion",
            "function_description": "A designed protein for binding target X",
        }
        with pytest.raises(ValueError, match="Invalid amino acid"):
            validate_payload("computational_biology", "protein_design", payload)

    def test_valid_protein_design_passes(self):
        """Valid protein design payload should pass."""
        payload = {
            "sequence": "ACDEFGHIKLMNPQRSTVWY" * 2,  # 40 chars, all valid
            "design_method": "rf_diffusion",
            "function_description": "A designed protein binder targeting IL-6 receptor interface",
        }
        result = validate_payload("computational_biology", "protein_design", payload)
        assert result["sequence"] == "ACDEFGHIKLMNPQRSTVWY" * 2

    def test_material_prediction_requires_structure(self):
        """Material prediction must have CIF or POSCAR structure."""
        payload = {
            "composition": "Li2FeSiO4",
            "predicted_properties": {"formation_energy_ev": -3.5},
            "prediction_method": "mace_mp",
            # Missing both structure_cif and structure_poscar
        }
        with pytest.raises(ValueError, match="structure"):
            validate_payload("materials_science", "material_prediction", payload)

    def test_material_prediction_with_cif_passes(self):
        """Material prediction with CIF structure should pass."""
        payload = {
            "composition": "Li2FeSiO4",
            "structure_cif": "data_Li2FeSiO4\n_cell_length_a 10.0",
            "predicted_properties": {"formation_energy_ev": -3.5},
            "prediction_method": "mace_mp",
        }
        result = validate_payload("materials_science", "material_prediction", payload)
        assert result["composition"] == "Li2FeSiO4"

    def test_material_prediction_functional_field(self):
        """New functional field should be accepted."""
        payload = {
            "composition": "Li2FeSiO4",
            "structure_cif": "data_Li2FeSiO4\n_cell_length_a 10.0",
            "predicted_properties": {"formation_energy_ev": -3.5},
            "prediction_method": "dft",
            "functional": "PBE",
        }
        result = validate_payload("materials_science", "material_prediction", payload)
        assert result["functional"] == "PBE"

    def test_pipeline_result_new_fields(self):
        """New pipeline result fields should be accepted."""
        payload = {
            "pipeline_type": "rnaseq_de",
            "input_data_description": "RNA-seq data from human liver tissue samples processed through standard pipeline",
            "results_summary": {"deg_count": 150, "upregulated": 80, "downregulated": 70},
            "reference_genome": "GRCh38",
            "pipeline_version": "3.14.0",
        }
        result = validate_payload("bioinformatics", "pipeline_result", payload)
        assert result["reference_genome"] == "GRCh38"
        assert result["pipeline_version"] == "3.14.0"

    def test_validate_payload_dispatches_correctly(self):
        """validate_payload should dispatch to correct schema based on domain/type."""
        schema = get_payload_schema("ml_ai", "ml_experiment")
        assert schema is not None
        assert schema.__name__ == "MLExperimentPayload"

    def test_unknown_domain_raises(self):
        """Unknown domain should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown domain"):
            validate_payload("quantum_computing", "theorem", {})

    def test_unknown_claim_type_raises(self):
        """Unknown claim type for valid domain should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown claim type"):
            validate_payload("mathematics", "nonexistent_type", {})

    def test_valid_ml_experiment_passes(self):
        """Valid ML experiment payload should pass."""
        payload = {
            "repository_url": "https://github.com/user/repo",
            "commit_hash": "a" * 40,
            "training_script": "train.py",
            "eval_script": "eval.py",
            "dataset_id": "mmlu",
            "claimed_metrics": {"accuracy": 0.95},
            "hardware_used": "NVIDIA A100 80GB x4",
            "training_time_hours": 24.5,
        }
        result = validate_payload("ml_ai", "ml_experiment", payload)
        assert result["commit_hash"] == "a" * 40
