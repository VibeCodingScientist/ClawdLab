"""Tests for ProtocolSigner content signing and verification."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from platform.security.protocol_integrity import ProtocolSigner


class TestSignContent:
    """Tests for ProtocolSigner.sign_content."""

    def test_sign_content_returns_content_and_checksum(self):
        """sign_content should return a tuple of (signed_content, checksum)."""
        signer = ProtocolSigner()
        raw = "title: My Protocol\n\nSome body text."

        with patch("platform.security.protocol_integrity.logger"):
            signed, checksum = signer.sign_content(raw, "1.0.0")

        assert isinstance(signed, str)
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA-256 hex digest length

    def test_signed_content_has_yaml_frontmatter_with_checksum(self):
        """Signed content should include YAML frontmatter containing the checksum."""
        signer = ProtocolSigner()
        raw = "Some protocol body text."

        with patch("platform.security.protocol_integrity.logger"):
            signed, checksum = signer.sign_content(raw, "1.0.0")

        assert signed.startswith("---\n")
        assert f"checksum: {checksum}" in signed
        assert "version: 1.0.0" in signed
        # Frontmatter should be closed
        parts = signed.split("---")
        # Should have at least opening ---, frontmatter, closing ---
        assert len(parts) >= 3

    def test_verify_content_returns_true_for_valid_content(self):
        """verify_content should return True when content is untampered."""
        signer = ProtocolSigner()
        raw = "A valid protocol body."

        with patch("platform.security.protocol_integrity.logger"):
            signed, checksum = signer.sign_content(raw, "2.0.0")
            result = signer.verify_content(signed, checksum)

        assert result is True

    def test_verify_content_returns_false_for_tampered_content(self):
        """verify_content should return False when content has been modified."""
        signer = ProtocolSigner()
        raw = "Original protocol body."

        with patch("platform.security.protocol_integrity.logger"):
            signed, checksum = signer.sign_content(raw, "1.0.0")

            # Tamper with the body
            tampered = signed.replace("Original protocol body.", "Tampered protocol body.")
            result = signer.verify_content(tampered, checksum)

        assert result is False

    def test_sign_content_with_existing_frontmatter_preserves_it(self):
        """When content already has frontmatter, sign_content should update it in place."""
        signer = ProtocolSigner()
        raw = "---\ntitle: Existing Title\nauthor: Test\n---\nBody text here."

        with patch("platform.security.protocol_integrity.logger"):
            signed, checksum = signer.sign_content(raw, "1.0.0")

        # The signed content should still contain the original frontmatter fields
        assert "title:" in signed
        assert "author:" in signed
        assert f"checksum: {checksum}" in signed
        assert "version:" in signed
        assert "Body text here." in signed

    def test_sign_content_without_frontmatter_creates_one(self):
        """When content has no frontmatter, sign_content should create one."""
        signer = ProtocolSigner()
        raw = "Plain body with no frontmatter."

        with patch("platform.security.protocol_integrity.logger"):
            signed, checksum = signer.sign_content(raw, "1.0.0")

        assert signed.startswith("---\n")
        assert f"checksum: {checksum}" in signed
        assert "version: 1.0.0" in signed
        assert "Plain body with no frontmatter." in signed

    def test_checksum_is_deterministic(self):
        """Same input content and version should always produce the same checksum."""
        signer = ProtocolSigner()
        raw = "Deterministic content check."

        with patch("platform.security.protocol_integrity.logger"):
            _, checksum1 = signer.sign_content(raw, "1.0.0")
            _, checksum2 = signer.sign_content(raw, "1.0.0")

        assert checksum1 == checksum2

    def test_different_versions_produce_different_checksums(self):
        """Different version strings should produce different checksums for the same content."""
        signer = ProtocolSigner()
        raw = "Same body content."

        with patch("platform.security.protocol_integrity.logger"):
            _, checksum_v1 = signer.sign_content(raw, "1.0.0")
            _, checksum_v2 = signer.sign_content(raw, "2.0.0")

        assert checksum_v1 != checksum_v2

    def test_verify_returns_false_without_frontmatter(self):
        """verify_content should return False if content has no frontmatter."""
        signer = ProtocolSigner()

        with patch("platform.security.protocol_integrity.logger"):
            result = signer.verify_content("No frontmatter here.", "abc123")

        assert result is False

    def test_verify_returns_false_without_version(self):
        """verify_content should return False if frontmatter has no version field."""
        signer = ProtocolSigner()
        content_without_version = "---\ntitle: No Version\n---\nBody."

        with patch("platform.security.protocol_integrity.logger"):
            result = signer.verify_content(content_without_version, "abc123")

        assert result is False
