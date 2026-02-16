# ===========================================
# ClawdLab — Computational Biology Verification Image
# ===========================================
# Single-stage build: Python 3.11 + BioPython + dssp + scipy
# ~250 MB final image, ~2 min build time.
#
# Usage:  docker build -f compbio.Dockerfile -t clawdlab/compbio-cpu .

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    dssp \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "biopython>=1.82,<2" \
    "numpy>=1.24,<2" \
    "scipy>=1.11,<2"

# Create non-root user
RUN groupadd --gid 1001 verifier \
    && useradd --uid 1001 --gid verifier --shell /bin/bash --create-home verifier

WORKDIR /workspace
RUN chown verifier:verifier /workspace

USER verifier

# Default: run a Python script passed as argument
# The adapter writes validation code to /workspace/validate.py then runs:
#   docker run --rm -v /tmp/compbio:/workspace clawdlab/compbio-cpu python /workspace/validate.py
CMD ["python", "--version"]
