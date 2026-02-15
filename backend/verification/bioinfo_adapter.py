"""Bioinformatics verification: git provenance + NCBI/UniProt APIs + scipy stats.

Validates pipeline provenance, cross-references sequence annotations against
public databases, and re-runs statistical tests with scipy.  No Docker.
"""
import asyncio
import os
import re
import time

import httpx

from backend.verification.base import (
    VerificationAdapter, VerificationResult,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
TIMEOUT = 30

# NCBI E-utilities base
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
ENSEMBL_BASE = "https://rest.ensembl.org"

# nf-core pipelines index
NFCORE_PIPELINES_URL = "https://nf-co.re/pipelines.json"

SUPPORTED_STAT_TESTS = {
    "ttest_ind", "ttest_rel", "mannwhitneyu", "wilcoxon",
    "chi2_contingency", "fisher_exact", "f_oneway",
    "pearsonr", "spearmanr",
}


class BioInfoAdapter(VerificationAdapter):
    domain = "bioinformatics"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "pipeline_result")

        if claim_type == "pipeline_result":
            return await self._verify_pipeline(task_result)
        elif claim_type == "sequence_annotation":
            return await self._verify_annotation(task_result)
        elif claim_type == "statistical_claim":
            return await self._verify_statistics(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    # ------------------------------------------------------------------
    # pipeline_result — provenance verification
    # ------------------------------------------------------------------

    async def _verify_pipeline(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        source = result.get("pipeline_source")
        commit = result.get("pipeline_commit")
        params = result.get("parameters", {})

        if not source or not commit:
            return VerificationResult.fail(self.domain, ["pipeline_source and pipeline_commit required"])

        component_scores: dict[str, float] = {}
        details: dict = {"claim_type": "pipeline_result", "pipeline": source, "commit": commit}

        # --- Check 1: Pipeline repo exists (0.20) ---
        repo_ok = await self._check_repo_exists(source)
        component_scores["repo_exists"] = 1.0 if repo_ok else 0.0
        details["repo_exists"] = repo_ok

        # --- Check 2: Commit/tag exists (0.20) ---
        commit_ok = False
        if repo_ok:
            commit_ok = await self._check_ref_exists(source, commit)
        component_scores["commit_exists"] = 1.0 if commit_ok else 0.0
        details["commit_exists"] = commit_ok

        # --- Check 3: Config file present (0.20) ---
        config_result = await self._check_config_files(source, commit)
        component_scores["config_present"] = config_result["score"]
        details["config"] = config_result.get("metrics", {})

        # --- Check 4: Pipeline in registry (0.20) ---
        registry_result = await self._check_pipeline_registry(source)
        component_scores["in_registry"] = registry_result["score"]
        details["registry"] = registry_result.get("metrics", {})

        # --- Check 5: Parameters valid (0.20) ---
        params_result = self._check_params_valid(params)
        component_scores["params_valid"] = params_result["score"]
        details["params"] = params_result.get("metrics", {})

        # --- Aggregate ---
        weights = {
            "repo_exists": 0.20,
            "commit_exists": 0.20,
            "config_present": 0.20,
            "in_registry": 0.20,
            "params_valid": 0.20,
        }
        score = sum(weights.get(k, 0) * component_scores.get(k, 0.0) for k in weights)
        score = min(1.0, round(score, 4))

        passed = score >= 0.6
        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=passed,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # sequence_annotation — NCBI/UniProt/Ensembl cross-reference
    # ------------------------------------------------------------------

    async def _verify_annotation(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        accession = result.get("accession", "")
        claimed_organism = result.get("organism")
        claimed_gene = result.get("gene_name")
        claimed_protein = result.get("protein_name")
        claimed_go_terms = result.get("go_terms", [])
        claimed_sequence = result.get("sequence", "")

        if not accession:
            return VerificationResult.fail(self.domain, ["accession required for annotation verification"])

        component_scores: dict[str, float] = {}
        details: dict = {"claim_type": "sequence_annotation", "accession": accession}
        warnings: list[str] = []

        # Route by accession pattern
        db_record = await self._fetch_db_record(accession)

        if db_record is None:
            elapsed = time.monotonic() - start
            return VerificationResult(
                passed=False, score=0.2,
                badge=VerificationResult.score_to_badge(0.2),
                domain=self.domain,
                details={**details, "note": "Accession not found in any database"},
                compute_time_seconds=elapsed,
            )

        details["source"] = db_record.get("source")

        # --- Check 1: Accession exists (0.25) ---
        component_scores["accession_exists"] = 1.0

        # --- Check 2: Organism matches (0.20) ---
        if claimed_organism and db_record.get("organism"):
            org_match = claimed_organism.lower().strip() == db_record["organism"].lower().strip()
            component_scores["organism_match"] = 1.0 if org_match else 0.0
            details["organism"] = {
                "claimed": claimed_organism,
                "database": db_record["organism"],
                "match": org_match,
            }
        else:
            component_scores["organism_match"] = 0.5  # neutral

        # --- Check 3: Gene/protein name matches (0.25) ---
        name_score = 0.5
        name_details: dict = {}
        db_gene = db_record.get("gene_name", "")
        db_protein = db_record.get("protein_name", "")

        if claimed_gene and db_gene:
            gene_match = claimed_gene.lower().strip() == db_gene.lower().strip()
            name_details["gene"] = {"claimed": claimed_gene, "database": db_gene, "match": gene_match}
            name_score = 1.0 if gene_match else 0.2
        if claimed_protein and db_protein:
            prot_match = claimed_protein.lower().strip() in db_protein.lower().strip()
            name_details["protein"] = {"claimed": claimed_protein, "database": db_protein, "match": prot_match}
            if prot_match:
                name_score = max(name_score, 1.0)

        component_scores["name_match"] = name_score
        details["names"] = name_details

        # --- Check 4: Functional annotations (GO terms) (0.20) ---
        go_score = 0.5
        if claimed_go_terms and db_record.get("go_terms"):
            db_go = set(db_record["go_terms"])
            claimed_go = set(claimed_go_terms)
            if claimed_go:
                overlap = claimed_go & db_go
                go_score = len(overlap) / len(claimed_go) if claimed_go else 0.5
                details["go_terms"] = {
                    "claimed": sorted(claimed_go_terms),
                    "database": sorted(db_record["go_terms"]),
                    "overlap": sorted(overlap),
                    "overlap_fraction": round(go_score, 4),
                }

        component_scores["go_terms"] = go_score

        # --- Check 5: Sequence identity (0.10) ---
        seq_score = 0.5
        if claimed_sequence and db_record.get("sequence"):
            db_seq = db_record["sequence"]
            min_len = min(len(claimed_sequence), len(db_seq))
            max_len = max(len(claimed_sequence), len(db_seq))
            if max_len > 0:
                matches = sum(1 for a, b in zip(claimed_sequence[:min_len], db_seq[:min_len]) if a == b)
                identity = matches / max_len
                seq_score = identity
                details["sequence"] = {
                    "claimed_length": len(claimed_sequence),
                    "database_length": len(db_seq),
                    "identity": round(identity, 4),
                }

        component_scores["sequence_identity"] = seq_score

        # --- Aggregate ---
        weights = {
            "accession_exists": 0.25,
            "organism_match": 0.20,
            "name_match": 0.25,
            "go_terms": 0.20,
            "sequence_identity": 0.10,
        }
        score = sum(weights.get(k, 0) * component_scores.get(k, 0.0) for k in weights)
        score = min(1.0, round(score, 4))

        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return VerificationResult(
            passed=score >= 0.5,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details=details,
            warnings=warnings,
            compute_time_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # statistical_claim — scipy re-computation
    # ------------------------------------------------------------------

    async def _verify_statistics(self, result: dict) -> VerificationResult:
        start = time.monotonic()

        claims = result.get("statistical_claims", [])
        if not claims:
            return VerificationResult.fail(self.domain, ["No statistical_claims provided"])

        all_results: list[dict] = []
        total_score = 0.0

        for claim in claims:
            claim_result = await asyncio.to_thread(self._verify_single_stat, claim)
            all_results.append(claim_result)
            total_score += claim_result["score"]

        avg_score = total_score / len(claims)
        avg_score = min(1.0, round(avg_score, 4))

        elapsed = time.monotonic() - start

        return VerificationResult(
            passed=avg_score >= 0.5,
            score=avg_score,
            badge=VerificationResult.score_to_badge(avg_score),
            domain=self.domain,
            details={
                "claim_type": "statistical_claim",
                "n_claims": len(claims),
                "individual_results": all_results,
            },
            compute_time_seconds=elapsed,
        )

    @staticmethod
    def _verify_single_stat(claim: dict) -> dict:
        """Re-run a single statistical test with scipy."""
        test_name = claim.get("test", "").lower()
        claimed_pvalue = claim.get("p_value")
        claimed_statistic = claim.get("test_statistic")
        data_a = claim.get("group_a") or claim.get("data_a") or claim.get("data", [])
        data_b = claim.get("group_b") or claim.get("data_b")
        alpha = claim.get("alpha", 0.05)
        tolerance = 0.05  # 5% relative tolerance

        component_scores: dict[str, float] = {}
        details: dict = {"test": test_name}

        # Check 1: Test type supported (0.10)
        if test_name not in SUPPORTED_STAT_TESTS:
            return {
                "score": 0.0,
                "details": {"error": f"Unsupported test: {test_name}. Supported: {sorted(SUPPORTED_STAT_TESTS)}"},
            }
        component_scores["test_supported"] = 1.0

        # Check 2 & 3: Re-run test (p-value 0.40, statistic 0.40)
        try:
            from scipy import stats
            import numpy as np

            arr_a = np.array(data_a, dtype=float) if data_a else None
            arr_b = np.array(data_b, dtype=float) if data_b else None

            stat_val = None
            p_val = None

            if test_name == "ttest_ind":
                if arr_a is None or arr_b is None:
                    return {"score": 0.1, "details": {"error": "ttest_ind requires group_a and group_b"}}
                stat_val, p_val = stats.ttest_ind(arr_a, arr_b)

            elif test_name == "ttest_rel":
                if arr_a is None or arr_b is None:
                    return {"score": 0.1, "details": {"error": "ttest_rel requires group_a and group_b"}}
                stat_val, p_val = stats.ttest_rel(arr_a, arr_b)

            elif test_name == "mannwhitneyu":
                if arr_a is None or arr_b is None:
                    return {"score": 0.1, "details": {"error": "mannwhitneyu requires group_a and group_b"}}
                stat_val, p_val = stats.mannwhitneyu(arr_a, arr_b, alternative="two-sided")

            elif test_name == "wilcoxon":
                if arr_a is None:
                    return {"score": 0.1, "details": {"error": "wilcoxon requires data"}}
                stat_val, p_val = stats.wilcoxon(arr_a)

            elif test_name == "chi2_contingency":
                table = claim.get("contingency_table") or data_a
                if table is None:
                    return {"score": 0.1, "details": {"error": "chi2_contingency requires contingency_table"}}
                table = np.array(table, dtype=float)
                stat_val, p_val, _, _ = stats.chi2_contingency(table)

            elif test_name == "fisher_exact":
                table = claim.get("contingency_table") or data_a
                if table is None:
                    return {"score": 0.1, "details": {"error": "fisher_exact requires contingency_table"}}
                table = np.array(table, dtype=float)
                stat_val, p_val = stats.fisher_exact(table)

            elif test_name == "f_oneway":
                groups = claim.get("groups") or [data_a]
                if data_b:
                    groups = [data_a, data_b]
                np_groups = [np.array(g, dtype=float) for g in groups]
                stat_val, p_val = stats.f_oneway(*np_groups)

            elif test_name == "pearsonr":
                if arr_a is None or arr_b is None:
                    return {"score": 0.1, "details": {"error": "pearsonr requires data_a and data_b"}}
                stat_val, p_val = stats.pearsonr(arr_a, arr_b)

            elif test_name == "spearmanr":
                if arr_a is None or arr_b is None:
                    return {"score": 0.1, "details": {"error": "spearmanr requires data_a and data_b"}}
                result_obj = stats.spearmanr(arr_a, arr_b)
                stat_val, p_val = result_obj.statistic, result_obj.pvalue

            details["reproduced_statistic"] = float(stat_val) if stat_val is not None else None
            details["reproduced_p_value"] = float(p_val) if p_val is not None else None

            # Compare p-value
            p_score = 0.5
            if claimed_pvalue is not None and p_val is not None:
                denom = max(abs(claimed_pvalue), 1e-15)
                p_dev = abs(claimed_pvalue - p_val) / denom
                p_score = 1.0 if p_dev <= tolerance else max(0.0, 1.0 - p_dev)
                details["p_value_deviation"] = round(p_dev, 6)
                details["p_value_match"] = p_dev <= tolerance

            component_scores["p_value"] = p_score

            # Compare test statistic
            stat_score = 0.5
            if claimed_statistic is not None and stat_val is not None:
                denom = max(abs(claimed_statistic), 1e-15)
                s_dev = abs(claimed_statistic - stat_val) / denom
                stat_score = 1.0 if s_dev <= tolerance else max(0.0, 1.0 - s_dev)
                details["statistic_deviation"] = round(s_dev, 6)
                details["statistic_match"] = s_dev <= tolerance

            component_scores["test_statistic"] = stat_score

        except Exception as e:
            component_scores["p_value"] = 0.0
            component_scores["test_statistic"] = 0.0
            details["error"] = str(e)

        # Check 4: Sample size adequate (0.10)
        n_a = len(data_a) if data_a else 0
        n_b = len(data_b) if data_b else 0
        min_n = 3 if test_name in ("pearsonr", "spearmanr") else 2
        adequate = n_a >= min_n and (n_b >= min_n if data_b else True)
        component_scores["sample_size"] = 1.0 if adequate else 0.3
        details["sample_sizes"] = {"n_a": n_a, "n_b": n_b, "adequate": adequate}

        # Weighted score
        weights = {
            "test_supported": 0.10,
            "p_value": 0.40,
            "test_statistic": 0.40,
            "sample_size": 0.10,
        }
        score = sum(weights.get(k, 0) * component_scores.get(k, 0.0) for k in weights)
        score = min(1.0, round(score, 4))

        details["component_scores"] = component_scores
        return {"score": score, "details": details}

    # ------------------------------------------------------------------
    # Git provenance helpers (for pipeline_result)
    # ------------------------------------------------------------------

    async def _check_repo_exists(self, repo_url: str) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "ls-remote", "--exit-code", repo_url,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=15)
            return proc.returncode == 0
        except (asyncio.TimeoutError, Exception):
            return False

    async def _check_ref_exists(self, repo_url: str, ref: str) -> bool:
        """Check if a specific commit/tag/branch exists."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "ls-remote", repo_url, ref,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            if stdout.decode().strip():
                return True
        except (asyncio.TimeoutError, Exception):
            pass

        # Try GitHub API for commit hash
        if "github.com" in repo_url:
            return await self._check_github_commit(repo_url, ref)

        return False

    async def _check_github_commit(self, repo_url: str, ref: str) -> bool:
        try:
            parts = repo_url.rstrip("/").rstrip(".git").split("github.com/")[-1]
            owner_repo = parts.split("/")
            if len(owner_repo) >= 2:
                owner, repo = owner_repo[0], owner_repo[1]
                headers = {}
                if GITHUB_TOKEN:
                    headers["Authorization"] = f"token {GITHUB_TOKEN}"
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    resp = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}",
                        headers=headers,
                    )
                    return resp.status_code == 200
        except Exception:
            pass
        return False

    async def _check_config_files(self, repo_url: str, ref: str) -> dict:
        """Check for pipeline config files (nextflow.config, Snakefile, etc.)."""
        config_files = {"nextflow.config", "Snakefile", "main.nf", "workflow.wdl", "conf/"}
        found: list[str] = []

        if "github.com" in repo_url:
            try:
                parts = repo_url.rstrip("/").rstrip(".git").split("github.com/")[-1]
                owner_repo = parts.split("/")
                if len(owner_repo) >= 2:
                    owner, repo = owner_repo[0], owner_repo[1]
                    headers = {}
                    if GITHUB_TOKEN:
                        headers["Authorization"] = f"token {GITHUB_TOKEN}"
                    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                        resp = await client.get(
                            f"https://api.github.com/repos/{owner}/{repo}/contents?ref={ref}",
                            headers=headers,
                        )
                        if resp.status_code == 200:
                            files = {f["name"] for f in resp.json() if isinstance(f, dict)}
                            found = [f for f in config_files if f in files]
            except Exception as e:
                logger.warning("config_files_check_failed", error=str(e))

        score = min(1.0, len(found) * 0.5) if found else 0.0
        return {
            "score": round(score, 4),
            "metrics": {"found": found, "checked": sorted(config_files)},
        }

    async def _check_pipeline_registry(self, source: str) -> dict:
        """Check if pipeline is in nf-core or WorkflowHub."""
        # nf-core check
        if "nf-core" in source:
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    resp = await client.get(NFCORE_PIPELINES_URL)
                    if resp.status_code == 200:
                        data = resp.json()
                        pipelines = data.get("remote_workflows", [])
                        pipeline_names = {p.get("name", "").lower() for p in pipelines}
                        # Extract pipeline name from source URL
                        name = source.rstrip("/").split("/")[-1].lower().replace("nf-core-", "")
                        if name in pipeline_names:
                            return {"score": 1.0, "metrics": {"registry": "nf-core", "name": name}}
            except Exception as e:
                logger.warning("nfcore_registry_check_failed", error=str(e))

        # Generic — if it's a known registry URL, score partial
        known_hosts = ["github.com/nf-core", "workflowhub.eu", "dockstore.org"]
        for host in known_hosts:
            if host in source:
                return {"score": 0.7, "metrics": {"registry": host, "note": "Known registry host"}}

        return {"score": 0.0, "metrics": {"note": "Not found in any pipeline registry"}}

    @staticmethod
    def _check_params_valid(params: dict) -> dict:
        """Basic parameter validation."""
        if not params:
            return {"score": 0.5, "metrics": {"note": "No parameters provided"}}

        issues: list[str] = []
        for key, val in params.items():
            if val is None:
                issues.append(f"Parameter '{key}' is null")
            if isinstance(val, str) and len(val) > 10000:
                issues.append(f"Parameter '{key}' value too long ({len(val)} chars)")

        score = 1.0 if not issues else max(0.3, 1.0 - 0.2 * len(issues))
        return {
            "score": round(score, 4),
            "metrics": {"n_params": len(params), "issues": issues},
        }

    # ------------------------------------------------------------------
    # Database lookup helpers (for sequence_annotation)
    # ------------------------------------------------------------------

    async def _fetch_db_record(self, accession: str) -> dict | None:
        """Route accession to the right database."""
        accession = accession.strip()

        # NCBI patterns: NM_, NP_, NR_, XM_, XP_, NC_
        if re.match(r"^[NX][MRPC]_\d+", accession):
            return await self._fetch_ncbi(accession)

        # UniProt patterns: P, Q, O followed by 5 alphanum, or newer format
        if re.match(r"^[APOQ]\d[A-Z0-9]{3}\d$", accession) or re.match(r"^[A-Z]\d[A-Z][A-Z0-9]{2}\d$", accession):
            return await self._fetch_uniprot(accession)

        # Ensembl patterns: ENSG, ENST, ENSP
        if re.match(r"^ENS[A-Z]*[GTRP]\d+", accession):
            return await self._fetch_ensembl(accession)

        # Try all in order
        for fetch_fn in [self._fetch_ncbi, self._fetch_uniprot, self._fetch_ensembl]:
            try:
                result = await fetch_fn(accession)
                if result:
                    return result
            except Exception:
                continue

        return None

    async def _fetch_ncbi(self, accession: str) -> dict | None:
        """Fetch record from NCBI E-utilities."""
        try:
            params = {
                "db": "nucleotide" if accession.startswith(("NM_", "NR_", "XM_", "NC_")) else "protein",
                "id": accession,
                "retmode": "json",
                "rettype": "docsum",
            }
            if NCBI_API_KEY:
                params["api_key"] = NCBI_API_KEY

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(f"{NCBI_BASE}/esummary.fcgi", params=params)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                result_data = data.get("result", {})
                uids = result_data.get("uids", [])
                if not uids:
                    return None
                doc = result_data.get(uids[0], {})
                return {
                    "source": "ncbi",
                    "organism": doc.get("organism", ""),
                    "gene_name": doc.get("gene", "") or doc.get("name", ""),
                    "protein_name": doc.get("title", ""),
                    "go_terms": [],  # NCBI summary doesn't include GO directly
                    "sequence": "",  # Would need efetch for full sequence
                }
        except Exception as e:
            logger.warning("ncbi_fetch_failed", error=str(e))
            return None

    async def _fetch_uniprot(self, accession: str) -> dict | None:
        """Fetch record from UniProt REST API."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(
                    f"{UNIPROT_BASE}/{accession}.json",
                    headers={"Accept": "application/json"},
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                organism = data.get("organism", {}).get("scientificName", "")
                genes = data.get("genes", [])
                gene_name = genes[0].get("geneName", {}).get("value", "") if genes else ""
                protein_name = data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "")

                # GO terms from cross-references
                go_terms = []
                for xref in data.get("uniProtKBCrossReferences", []):
                    if xref.get("database") == "GO":
                        go_terms.append(xref.get("id", ""))

                # Sequence
                sequence = data.get("sequence", {}).get("value", "")

                return {
                    "source": "uniprot",
                    "organism": organism,
                    "gene_name": gene_name,
                    "protein_name": protein_name,
                    "go_terms": go_terms,
                    "sequence": sequence,
                }
        except Exception as e:
            logger.warning("uniprot_fetch_failed", error=str(e))
            return None

    async def _fetch_ensembl(self, accession: str) -> dict | None:
        """Fetch record from Ensembl REST API."""
        try:
            # Determine lookup type
            if "ENSG" in accession or "G0" in accession:
                endpoint = f"/lookup/id/{accession}"
            elif "ENST" in accession:
                endpoint = f"/lookup/id/{accession}"
            elif "ENSP" in accession:
                endpoint = f"/lookup/id/{accession}"
            else:
                endpoint = f"/lookup/id/{accession}"

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.get(
                    f"{ENSEMBL_BASE}{endpoint}",
                    params={"content-type": "application/json", "expand": "1"},
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                return {
                    "source": "ensembl",
                    "organism": data.get("species", ""),
                    "gene_name": data.get("display_name", ""),
                    "protein_name": data.get("description", ""),
                    "go_terms": [],  # Would need separate ontology lookup
                    "sequence": "",  # Would need sequence endpoint
                }
        except Exception as e:
            logger.warning("ensembl_fetch_failed", error=str(e))
            return None
