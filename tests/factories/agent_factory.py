"""Agent test data factory."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass
class AgentFactory:
    """Factory for creating Agent test instances."""

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        agent_id: str | None = None,
        display_name: str | None = None,
        agent_type: str = "openclaw",
        status: str = "active",
        public_key: str | None = None,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create an agent data dictionary with sensible defaults.

        Returns a dictionary since Agent may be either an ORM model or
        a dataclass depending on context.
        """
        cls._counter = getattr(cls, "_counter", 0) + 1

        return {
            "agent_id": agent_id or str(uuid4()),
            "display_name": display_name or f"TestAgent_{cls._counter}",
            "agent_type": agent_type,
            "status": status,
            "public_key": public_key or cls._generate_mock_public_key(),
            "capabilities": capabilities or ["mathematics"],
            "metadata": metadata or {
                "version": "1.0.0",
                "description": f"Test agent {cls._counter}",
            },
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            **kwargs,
        }

    @classmethod
    def create_with_keypair(cls, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create an agent with a real cryptographic keypair.

        Returns a tuple of (agent_data, keypair_data).
        """
        try:
            from platform.shared.utils.crypto import generate_agent_keypair

            private_key, identity = generate_agent_keypair()
            keypair = {
                "private_key": private_key,
                "identity": identity,
                "agent_id": identity.agent_id,
                "public_key_pem": identity.get_public_key_pem(),
            }

            agent_data = cls.create(
                agent_id=keypair["agent_id"],
                public_key=keypair["public_key_pem"],
                **kwargs,
            )

            return agent_data, keypair

        except ImportError:
            # Fallback if crypto module is not available
            agent_data = cls.create(**kwargs)
            keypair = {
                "agent_id": agent_data["agent_id"],
                "public_key_pem": agent_data["public_key"],
            }
            return agent_data, keypair

    @classmethod
    def create_mathematics_agent(cls, **kwargs: Any) -> dict[str, Any]:
        """Create an agent specialized in mathematics."""
        return cls.create(
            display_name=kwargs.pop("display_name", "MathAgent"),
            capabilities=kwargs.pop("capabilities", ["mathematics"]),
            metadata=kwargs.pop("metadata", {
                "specialization": "theorem_proving",
                "tools": ["lean4", "coq", "z3"],
            }),
            **kwargs,
        )

    @classmethod
    def create_ml_agent(cls, **kwargs: Any) -> dict[str, Any]:
        """Create an agent specialized in machine learning."""
        return cls.create(
            display_name=kwargs.pop("display_name", "MLAgent"),
            capabilities=kwargs.pop("capabilities", ["ml_ai"]),
            metadata=kwargs.pop("metadata", {
                "specialization": "deep_learning",
                "frameworks": ["pytorch", "tensorflow"],
            }),
            **kwargs,
        )

    @classmethod
    def create_biology_agent(cls, **kwargs: Any) -> dict[str, Any]:
        """Create an agent specialized in computational biology."""
        return cls.create(
            display_name=kwargs.pop("display_name", "BioAgent"),
            capabilities=kwargs.pop("capabilities", ["computational_biology"]),
            metadata=kwargs.pop("metadata", {
                "specialization": "protein_structure",
                "tools": ["alphafold", "esmfold"],
            }),
            **kwargs,
        )

    @classmethod
    def create_multi_domain_agent(cls, **kwargs: Any) -> dict[str, Any]:
        """Create an agent with multiple domain capabilities."""
        return cls.create(
            display_name=kwargs.pop("display_name", "MultiDomainAgent"),
            capabilities=kwargs.pop("capabilities", [
                "mathematics",
                "ml_ai",
                "computational_biology",
            ]),
            metadata=kwargs.pop("metadata", {
                "specialization": "interdisciplinary",
            }),
            **kwargs,
        )

    @classmethod
    def create_batch(cls, count: int, **kwargs: Any) -> list[dict[str, Any]]:
        """Create multiple agent instances."""
        return [cls.create(**kwargs) for _ in range(count)]

    @classmethod
    def _generate_mock_public_key(cls) -> str:
        """Generate a mock public key string for testing."""
        import base64
        import secrets

        # Generate random bytes and encode as base64 to simulate a key
        random_bytes = secrets.token_bytes(32)
        encoded = base64.b64encode(random_bytes).decode()

        return f"-----BEGIN PUBLIC KEY-----\n{encoded}\n-----END PUBLIC KEY-----"


@dataclass
class AgentCapabilityFactory:
    """Factory for creating AgentCapability test instances."""

    _counter: int = field(default=0, repr=False)

    VALID_DOMAINS = [
        "mathematics",
        "ml_ai",
        "computational_biology",
        "materials_science",
        "bioinformatics",
    ]

    CAPABILITY_LEVELS = ["basic", "intermediate", "advanced", "expert"]

    @classmethod
    def create(
        cls,
        capability_id: str | None = None,
        agent_id: str | None = None,
        domain: str = "mathematics",
        capability_level: str = "basic",
        verified_at: datetime | None = None,
        verification_method: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a capability data dictionary."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        return {
            "capability_id": capability_id or str(uuid4()),
            "agent_id": agent_id or str(uuid4()),
            "domain": domain,
            "capability_level": capability_level,
            "verified_at": verified_at,
            "verification_method": verification_method,
            **kwargs,
        }

    @classmethod
    def create_verified(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a verified capability."""
        return cls.create(
            verified_at=_utcnow(),
            verification_method=kwargs.pop("verification_method", "benchmark_test"),
            **kwargs,
        )

    @classmethod
    def create_all_domains(cls, agent_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Create capabilities for all valid domains for an agent."""
        return [
            cls.create(agent_id=agent_id, domain=domain, **kwargs)
            for domain in cls.VALID_DOMAINS
        ]


@dataclass
class AgentReputationFactory:
    """Factory for creating AgentReputation test instances."""

    @classmethod
    def create(
        cls,
        agent_id: str | None = None,
        total_karma: int = 0,
        verification_karma: int = 0,
        citation_karma: int = 0,
        challenge_karma: int = 0,
        service_karma: int = 0,
        domain_karma: dict[str, int] | None = None,
        claims_submitted: int = 0,
        claims_verified: int = 0,
        claims_failed: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a reputation data dictionary."""
        return {
            "agent_id": agent_id or str(uuid4()),
            "total_karma": total_karma,
            "verification_karma": verification_karma,
            "citation_karma": citation_karma,
            "challenge_karma": challenge_karma,
            "service_karma": service_karma,
            "domain_karma": domain_karma or {},
            "claims_submitted": claims_submitted,
            "claims_verified": claims_verified,
            "claims_failed": claims_failed,
            "claims_disputed": kwargs.pop("claims_disputed", 0),
            "claims_retracted": kwargs.pop("claims_retracted", 0),
            "challenges_made": kwargs.pop("challenges_made", 0),
            "challenges_won": kwargs.pop("challenges_won", 0),
            "challenges_lost": kwargs.pop("challenges_lost", 0),
            "verifications_performed": kwargs.pop("verifications_performed", 0),
            "success_rate": kwargs.pop("success_rate", None),
            "impact_score": kwargs.pop("impact_score", None),
            "updated_at": _utcnow(),
            **kwargs,
        }

    @classmethod
    def create_high_reputation(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a high reputation profile."""
        return cls.create(
            total_karma=10000,
            verification_karma=5000,
            citation_karma=3000,
            challenge_karma=1000,
            service_karma=1000,
            claims_submitted=100,
            claims_verified=95,
            claims_failed=5,
            success_rate=0.95,
            impact_score=8.5,
            **kwargs,
        )

    @classmethod
    def create_new_agent_reputation(cls, **kwargs: Any) -> dict[str, Any]:
        """Create reputation for a new agent (all zeros)."""
        return cls.create(**kwargs)


@dataclass
class AgentTokenFactory:
    """Factory for creating AgentToken test instances."""

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        token_id: str | None = None,
        agent_id: str | None = None,
        token_hash: str | None = None,
        token_prefix: str | None = None,
        name: str | None = None,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
        revoked_at: datetime | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create an agent token data dictionary."""
        import hashlib
        import secrets
        from datetime import timedelta

        cls._counter = getattr(cls, "_counter", 0) + 1

        raw_token = secrets.token_urlsafe(32)

        return {
            "token_id": token_id or str(uuid4()),
            "agent_id": agent_id or str(uuid4()),
            "token_hash": token_hash or hashlib.sha256(raw_token.encode()).hexdigest(),
            "token_prefix": token_prefix or f"srp_{raw_token[:8]}",
            "name": name or f"token_{cls._counter}",
            "scopes": scopes or ["read", "write"],
            "created_at": _utcnow(),
            "expires_at": expires_at or _utcnow() + timedelta(days=365),
            "last_used_at": None,
            "revoked_at": revoked_at,
            **kwargs,
        }

    @classmethod
    def create_with_raw_token(cls, **kwargs: Any) -> tuple[dict[str, Any], str]:
        """Create a token and return both the token data and raw token value."""
        import hashlib
        import secrets

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        token_data = cls.create(
            token_hash=token_hash,
            token_prefix=f"srp_{raw_token[:8]}",
            **kwargs,
        )

        return token_data, raw_token

    @classmethod
    def create_expired(cls, **kwargs: Any) -> dict[str, Any]:
        """Create an expired token."""
        from datetime import timedelta

        return cls.create(
            expires_at=_utcnow() - timedelta(days=1),
            **kwargs,
        )

    @classmethod
    def create_revoked(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a revoked token."""
        return cls.create(
            revoked_at=_utcnow(),
            **kwargs,
        )
