"""Tests for chemistry domain adapter."""
import pytest
from unittest.mock import patch, AsyncMock

from backend.verification.chemistry_adapter import ChemistryAdapter, RDKIT_AVAILABLE


@pytest.fixture
def adapter():
    return ChemistryAdapter()


class TestBasic:
    def test_domain(self, adapter):
        assert adapter.domain == "chemistry"


@pytest.mark.asyncio
class TestReactionMechanism:
    async def test_unknown_claim_type(self, adapter):
        result = await adapter.verify({"claim_type": "unknown"}, {})
        assert result.passed is False
        assert "Unknown claim_type" in result.errors[0]

    async def test_no_reactants_or_products(self, adapter):
        result = await adapter.verify({"claim_type": "reaction_mechanism"}, {})
        assert result.passed is False

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    async def test_valid_reaction(self, adapter):
        result = await adapter.verify({
            "claim_type": "reaction_mechanism",
            "smiles": "CC.O>>CCO",
        }, {})
        assert result.score > 0.0
        assert result.details["claim_type"] == "reaction_mechanism"

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    async def test_invalid_smiles(self, adapter):
        result = await adapter.verify({
            "claim_type": "reaction_mechanism",
            "reactants": ["INVALID_SMILES"],
            "products": ["ALSO_INVALID"],
        }, {})
        assert result.details["smiles_validity"]["valid"] == 0


class TestSMILESValidity:
    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_valid_smiles(self):
        result = ChemistryAdapter._check_smiles_validity(["CCO", "CC(=O)O", "c1ccccc1"])
        assert result["score"] == 1.0
        assert result["valid"] == 3

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_invalid_smiles(self):
        result = ChemistryAdapter._check_smiles_validity(["INVALID", "ALSO_BAD"])
        assert result["score"] == 0.0

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_mixed_smiles(self):
        result = ChemistryAdapter._check_smiles_validity(["CCO", "INVALID"])
        assert result["score"] == 0.5

    def test_without_rdkit(self):
        if not RDKIT_AVAILABLE:
            result = ChemistryAdapter._check_smiles_validity(["CCO"])
            assert result["score"] == 0.5


class TestStoichiometry:
    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_balanced(self):
        # Simple: ethanol formation C2H6 + O -> C2H5OH (simplified, won't balance perfectly)
        result = ChemistryAdapter._check_stoichiometry(["CCO"], ["CCO"])
        assert result["score"] == 1.0

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_invalid_smiles_returns_zero(self):
        result = ChemistryAdapter._check_stoichiometry(["INVALID"], ["INVALID"])
        assert result["score"] == 0.0


@pytest.mark.asyncio
class TestMolecularProperty:
    async def test_no_smiles(self, adapter):
        result = await adapter.verify({
            "claim_type": "molecular_property",
        }, {})
        assert result.passed is False

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    @patch("backend.verification.chemistry_adapter.ChemistryAdapter._check_pubchem")
    @patch("backend.verification.chemistry_adapter.ChemistryAdapter._check_chembl")
    async def test_valid_molecule(self, mock_chembl, mock_pubchem, adapter):
        mock_pubchem.return_value = {"score": 0.8, "found": True}
        mock_chembl.return_value = {"score": 0.7, "found": True}

        result = await adapter.verify({
            "claim_type": "molecular_property",
            "smiles": "CCO",
            "claimed_properties": {"molecular_weight": 46.07},
        }, {})
        assert result.score > 0.0
        assert result.details["claim_type"] == "molecular_property"

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    async def test_invalid_smiles(self, adapter):
        result = await adapter.verify({
            "claim_type": "molecular_property",
            "smiles": "INVALID_SMILES_STRING",
        }, {})
        assert result.passed is False


@pytest.mark.asyncio
class TestRetrosynthesis:
    async def test_no_precursors(self, adapter):
        result = await adapter.verify({
            "claim_type": "retrosynthesis",
            "products": ["CCO"],
        }, {})
        assert result.passed is False

    async def test_no_products(self, adapter):
        result = await adapter.verify({
            "claim_type": "retrosynthesis",
            "precursors": ["CC", "O"],
        }, {})
        assert result.passed is False

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    async def test_valid_retrosynthesis(self, adapter):
        result = await adapter.verify({
            "claim_type": "retrosynthesis",
            "precursors": ["CC=O", "CC"],
            "products": ["CC(O)CC"],
        }, {})
        assert result.score > 0.0
        assert result.details["claim_type"] == "retrosynthesis"


class TestPropertyRanges:
    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_matching_molecular_weight(self):
        result = ChemistryAdapter._check_property_ranges(
            "CCO",
            {"molecular_weight": 46.07},
        )
        assert result["score"] > 0.0
        assert "computed_properties" in result

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_invalid_smiles(self):
        result = ChemistryAdapter._check_property_ranges(
            "INVALID",
            {"molecular_weight": 100.0},
        )
        assert result["score"] == 0.0


class TestAtomConservation:
    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_conserved(self):
        result = ChemistryAdapter._check_atom_conservation(["CC", "O"], ["CCO"])
        assert result["conserved"] is True
        assert result["score"] == 1.0

    @pytest.mark.skipif(not RDKIT_AVAILABLE, reason="rdkit not installed")
    def test_atoms_lost(self):
        # Product has more atoms than precursors
        result = ChemistryAdapter._check_atom_conservation(["C"], ["CCCCCC"])
        assert result["score"] < 1.0
