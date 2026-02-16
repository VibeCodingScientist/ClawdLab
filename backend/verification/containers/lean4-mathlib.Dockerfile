# ===========================================
# ClawdLab — Lean 4 + Mathlib Verification Image
# ===========================================
# Multi-stage build: builder compiles the toolchain + Mathlib cache,
# runtime is a minimal Ubuntu image (~2 GB final).
#
# Build time: ~30 minutes (Mathlib compilation)
# Usage:  docker build -f lean4-mathlib.Dockerfile -t clawdlab/lean4-mathlib .

# === BUILDER ===
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install elan (Lean version manager) + Lean 4 v4.3.0
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | \
    sh -s -- -y --default-toolchain leanprover/lean4:v4.3.0

ENV PATH="/root/.elan/bin:$PATH"

# Clone and build Mathlib4 (this takes ~20-30 minutes)
RUN git clone --depth 1 https://github.com/leanprover-community/mathlib4.git /opt/mathlib4 && \
    cd /opt/mathlib4 && \
    lake build

# === RUNTIME ===
FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libgmp10 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1001 verifier \
    && useradd --uid 1001 --gid verifier --shell /bin/bash --create-home verifier

# Copy Lean toolchain and Mathlib from builder
COPY --from=builder /root/.elan /home/verifier/.elan
COPY --from=builder /opt/mathlib4 /opt/mathlib4

# Fix ownership
RUN chown -R verifier:verifier /home/verifier/.elan /opt/mathlib4

ENV PATH="/home/verifier/.elan/bin:$PATH" \
    MATHLIB_PATH="/opt/mathlib4" \
    ELAN_HOME="/home/verifier/.elan"

WORKDIR /workspace
RUN chown verifier:verifier /workspace

USER verifier

# Default: check a .lean file passed as argument
# The adapter writes proof_code to /workspace/Proof.lean then runs:
#   docker run --rm -v /tmp/proof:/workspace clawdlab/lean4-mathlib lean /workspace/Proof.lean
CMD ["lean", "--version"]
