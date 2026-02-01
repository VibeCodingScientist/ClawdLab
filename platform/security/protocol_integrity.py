"""Protocol Integrity Service.

Provides content signing and verification for research protocols using
SHA-256 checksums injected into YAML frontmatter. This ensures protocol
content has not been tampered with after publication.

Usage:
    signer = ProtocolSigner()
    signed_content, checksum = signer.sign_content(raw_yaml, "1.0.0")
    is_valid = signer.verify_content(signed_content, checksum)
"""

from __future__ import annotations

import hashlib
import re

import yaml

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Regex to match YAML frontmatter delimited by ---
_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)

# Regex to extract checksum from frontmatter
_CHECKSUM_RE = re.compile(r"^checksum:\s*([a-fA-F0-9]{64})\s*$", re.MULTILINE)


class ProtocolSigner:
    """Sign and verify protocol content with SHA-256 checksums."""

    @staticmethod
    def sign_content(content: str, version: str) -> tuple[str, str]:
        """Compute SHA-256 checksum and inject it into YAML frontmatter.

        If the content already has YAML frontmatter (delimited by ``---``),
        the checksum and version fields are added/updated within it.
        If there is no frontmatter, one is created.

        The checksum is computed on the content *without* the checksum
        field itself, ensuring the checksum is self-consistent.

        Args:
            content: The protocol content (may or may not have frontmatter).
            version: The protocol version string.

        Returns:
            Tuple of (content_with_checksum, checksum).
        """
        # Remove existing checksum line from content before hashing
        clean_content = _CHECKSUM_RE.sub("", content).strip()

        # Compute checksum on the clean content + version
        hash_input = f"{clean_content}\n---version:{version}---"
        checksum = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        # Inject into frontmatter
        frontmatter_match = _FRONTMATTER_RE.match(content)

        if frontmatter_match:
            # Parse existing frontmatter
            existing_fm = frontmatter_match.group(1)
            try:
                fm_data = yaml.safe_load(existing_fm) or {}
            except yaml.YAMLError:
                fm_data = {}

            fm_data["checksum"] = checksum
            fm_data["version"] = version

            # Rebuild content with updated frontmatter
            body = content[frontmatter_match.end():]
            new_fm = yaml.dump(fm_data, default_flow_style=False).strip()
            signed_content = f"---\n{new_fm}\n---\n{body}"
        else:
            # No existing frontmatter; create one
            fm_data = {
                "checksum": checksum,
                "version": version,
            }
            new_fm = yaml.dump(fm_data, default_flow_style=False).strip()
            signed_content = f"---\n{new_fm}\n---\n{content}"

        logger.info(
            "protocol_signed",
            version=version,
            checksum=checksum[:16] + "...",
        )

        return signed_content, checksum

    @staticmethod
    def verify_content(signed_content: str, expected_checksum: str) -> bool:
        """Verify that signed content matches the expected checksum.

        Extracts the version from frontmatter, strips the checksum line,
        and recomputes the hash to compare against the expected value.

        Args:
            signed_content: The content with embedded checksum in frontmatter.
            expected_checksum: The checksum to verify against.

        Returns:
            True if the computed checksum matches the expected one.
        """
        # Extract frontmatter
        frontmatter_match = _FRONTMATTER_RE.match(signed_content)
        if not frontmatter_match:
            logger.warning("verify_failed_no_frontmatter")
            return False

        existing_fm = frontmatter_match.group(1)
        try:
            fm_data = yaml.safe_load(existing_fm) or {}
        except yaml.YAMLError:
            logger.warning("verify_failed_invalid_yaml")
            return False

        version = fm_data.get("version")
        if not version:
            logger.warning("verify_failed_no_version")
            return False

        # Remove checksum line and recompute
        clean_content = _CHECKSUM_RE.sub("", signed_content).strip()
        hash_input = f"{clean_content}\n---version:{version}---"
        computed_checksum = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        is_valid = computed_checksum == expected_checksum
        if not is_valid:
            logger.warning(
                "protocol_verification_failed",
                expected=expected_checksum[:16] + "...",
                computed=computed_checksum[:16] + "...",
            )
        else:
            logger.info(
                "protocol_verified",
                version=version,
                checksum=expected_checksum[:16] + "...",
            )

        return is_valid
