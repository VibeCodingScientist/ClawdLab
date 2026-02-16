"""Tests for task payload validation."""
import pytest
from uuid import uuid4

from backend.payloads.task_payloads import (
    AnalysisResult,
    BioinformaticsPayload,
    ChemistryPayload,
    CompBioPayload,
    CritiqueResult,
    DeepResearchResult,
    LiteratureReviewResult,
    MaterialsSciencePayload,
    MathematicsPayload,
    MLAIPayload,
    PhysicsPayload,
    SynthesisResult,
    validate_task_result,
)


class TestLiteratureReviewResult:
    def test_valid(self):
        data = {
            "papers": [{"title": "Paper 1", "authors": ["A"], "url": "http://x", "year": 2024, "abstract": "..."}],
            "summary": "A" * 50,
        }
        model = LiteratureReviewResult.model_validate(data)
        assert len(model.papers) == 1

    def test_invalid_empty_papers(self):
        data = {"papers": [], "summary": "A" * 50}
        with pytest.raises(Exception):
            LiteratureReviewResult.model_validate(data)

    def test_invalid_short_summary(self):
        data = {"papers": [{"title": "P"}], "summary": "Short"}
        with pytest.raises(Exception):
            LiteratureReviewResult.model_validate(data)


class TestAnalysisResult:
    def test_valid(self):
        data = {"methodology": "A" * 20}
        model = AnalysisResult.model_validate(data)
        assert model.metrics == {}

    def test_invalid_short_methodology(self):
        data = {"methodology": "short"}
        with pytest.raises(Exception):
            AnalysisResult.model_validate(data)


class TestCritiqueResult:
    def test_valid(self):
        data = {
            "target_task_id": str(uuid4()),
            "issues": ["Issue 1"],
            "severity": "major",
        }
        model = CritiqueResult.model_validate(data)
        assert model.severity == "major"

    def test_invalid_severity(self):
        data = {
            "target_task_id": str(uuid4()),
            "issues": ["Issue 1"],
            "severity": "low",
        }
        with pytest.raises(Exception):
            CritiqueResult.model_validate(data)


class TestSynthesisResult:
    def test_valid(self):
        data = {
            "document": "A" * 100,
            "sources": [str(uuid4())],
        }
        model = SynthesisResult.model_validate(data)
        assert len(model.sources) == 1


class TestDeepResearchResult:
    def test_valid(self):
        data = {
            "methodology": "A" * 20,
            "findings": "B" * 100,
        }
        model = DeepResearchResult.model_validate(data)
        assert model.data == {}


class TestMathematicsPayload:
    def test_valid_theorem(self):
        data = {
            "claim_type": "theorem",
            "proof_code": "theorem test : True := by trivial",
        }
        model = MathematicsPayload.model_validate(data)
        assert model.claim_type == "theorem"
        assert model.proof_system == "lean4"  # default

    def test_valid_conjecture(self):
        data = {
            "claim_type": "conjecture",
            "proof_code": "-- conjecture code here, placeholder",
        }
        model = MathematicsPayload.model_validate(data)
        assert model.claim_type == "conjecture"

    def test_valid_coq(self):
        data = {
            "claim_type": "theorem",
            "proof_system": "coq",
            "proof_code": "Theorem test : True. Proof. trivial. Qed.",
        }
        model = MathematicsPayload.model_validate(data)
        assert model.proof_system == "coq"

    def test_valid_isabelle(self):
        data = {
            "claim_type": "theorem",
            "proof_system": "isabelle",
            "proof_code": "lemma test: True by simp",
            "theory_name": "MyTheory",
        }
        model = MathematicsPayload.model_validate(data)
        assert model.proof_system == "isabelle"
        assert model.theory_name == "MyTheory"

    def test_invalid_proof_system(self):
        data = {"claim_type": "theorem", "proof_system": "agda", "proof_code": "A" * 10}
        with pytest.raises(Exception):
            MathematicsPayload.model_validate(data)

    def test_invalid_claim_type(self):
        data = {"claim_type": "lemma", "proof_code": "A" * 10}
        with pytest.raises(Exception):
            MathematicsPayload.model_validate(data)


class TestMLAIPayload:
    def test_valid_benchmark(self):
        data = {
            "claim_type": "benchmark_result",
            "model_id": "meta-llama/Llama-3-8B",
            "benchmark": "mmlu",
            "metrics": {"accuracy": 0.654},
        }
        model = MLAIPayload.model_validate(data)
        assert model.model_id == "meta-llama/Llama-3-8B"
        assert model.sample_size == 20  # default

    def test_valid_benchmark_live(self):
        data = {
            "claim_type": "benchmark_live",
            "model_id": "test/model",
            "benchmark": "mmlu",
            "sample_size": 30,
        }
        model = MLAIPayload.model_validate(data)
        assert model.claim_type == "benchmark_live"
        assert model.sample_size == 30

    def test_sample_size_bounds(self):
        # Too small
        with pytest.raises(Exception):
            MLAIPayload.model_validate({"claim_type": "benchmark_live", "sample_size": 2})
        # Too large
        with pytest.raises(Exception):
            MLAIPayload.model_validate({"claim_type": "benchmark_live", "sample_size": 100})

    def test_valid_architecture(self):
        data = {
            "claim_type": "architecture",
            "code": "import torch\nclass Model(torch.nn.Module): pass",
            "param_count": 1000000,
        }
        model = MLAIPayload.model_validate(data)
        assert model.param_count == 1000000


class TestCompBioPayload:
    def test_valid_structure(self):
        data = {
            "claim_type": "structure_prediction",
            "sequence": "MKFLILLFNILCLFPVLAAD",
            "method": "esmfold",
        }
        model = CompBioPayload.model_validate(data)
        assert model.method == "esmfold"


class TestMaterialsSciencePayload:
    def test_valid(self):
        data = {
            "claim_type": "material_prediction",
            "formula": "Li2FeSiO4",
            "structure_cif": "data_test\n_cell_length_a 10.0",
        }
        model = MaterialsSciencePayload.model_validate(data)
        assert model.formula == "Li2FeSiO4"


class TestBioinformaticsPayload:
    def test_valid_pipeline(self):
        data = {
            "claim_type": "pipeline_result",
            "pipeline_source": "https://github.com/nf-core/rnaseq",
            "pipeline_commit": "3.12.0",
        }
        model = BioinformaticsPayload.model_validate(data)
        assert model.pipeline_source == "https://github.com/nf-core/rnaseq"


class TestValidateTaskResult:
    def test_valid_literature_review(self):
        result = {
            "papers": [{"title": "P1"}],
            "summary": "A" * 50,
        }
        valid, errors = validate_task_result("literature_review", "general", result)
        assert valid is True
        assert errors == []

    def test_invalid_literature_review(self):
        result = {"papers": [], "summary": "short"}
        valid, errors = validate_task_result("literature_review", "general", result)
        assert valid is False
        assert len(errors) > 0

    def test_unknown_task_type(self):
        valid, errors = validate_task_result("unknown_type", "general", {"key": "val"})
        assert valid is True  # No model to validate against

    def test_domain_validation_non_strict(self):
        result = {
            "methodology": "A" * 20,
            "claim_type": "theorem",
            "proof_code": "theorem test : True := by trivial",
        }
        valid, errors = validate_task_result("analysis", "mathematics", result)
        # Non-strict: domain validation errors are ignored
        assert valid is True

    def test_domain_validation_strict(self):
        result = {
            "methodology": "A" * 20,
            "claim_type": "invalid_type",
            "proof_code": "short",
        }
        valid, errors = validate_task_result("analysis", "mathematics", result, strict=True)
        assert valid is False
        assert any("Domain payload" in e for e in errors)

    def test_domain_fields_not_present_skips_validation(self):
        result = {"methodology": "A" * 20}
        valid, errors = validate_task_result("analysis", "mathematics", result)
        # No domain fields present, so domain validation is skipped
        assert valid is True


class TestChemistryPayload:
    def test_valid_reaction(self):
        data = {
            "claim_type": "reaction_mechanism",
            "smiles": "CC.O>>CCO",
        }
        model = ChemistryPayload.model_validate(data)
        assert model.claim_type == "reaction_mechanism"

    def test_valid_molecular_property(self):
        data = {
            "claim_type": "molecular_property",
            "smiles": "CCO",
            "claimed_properties": {"molecular_weight": 46.07},
        }
        model = ChemistryPayload.model_validate(data)
        assert model.smiles == "CCO"

    def test_valid_retrosynthesis(self):
        data = {
            "claim_type": "retrosynthesis",
            "precursors": ["CC=O", "CC"],
            "products": ["CC(O)CC"],
        }
        model = ChemistryPayload.model_validate(data)
        assert len(model.precursors) == 2

    def test_invalid_claim_type(self):
        data = {"claim_type": "alchemy"}
        with pytest.raises(Exception):
            ChemistryPayload.model_validate(data)


class TestPhysicsPayload:
    def test_valid_simulation(self):
        data = {
            "claim_type": "numerical_simulation",
            "conservation_quantities": {"energy": {"initial": 100, "final": 100}},
        }
        model = PhysicsPayload.model_validate(data)
        assert model.claim_type == "numerical_simulation"

    def test_valid_derivation(self):
        data = {
            "claim_type": "analytical_derivation",
            "expression": "E = m * c**2",
            "units": {"E": "joule", "m": "kilogram", "c": "meter/second"},
        }
        model = PhysicsPayload.model_validate(data)
        assert model.expression == "E = m * c**2"

    def test_valid_dimensional_analysis(self):
        data = {
            "claim_type": "dimensional_analysis",
            "lhs": "F",
            "rhs": "m * a",
            "units": {"F": "newton", "m": "kilogram", "a": "meter/second**2"},
        }
        model = PhysicsPayload.model_validate(data)
        assert model.lhs == "F"

    def test_invalid_claim_type(self):
        data = {"claim_type": "string_theory"}
        with pytest.raises(Exception):
            PhysicsPayload.model_validate(data)
