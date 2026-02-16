FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git make gcc g++ && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "numpy>=1.24,<2" "scipy>=1.11,<2" "pandas>=2.0,<3" \
    "scikit-learn>=1.3,<2" "matplotlib>=3.7,<4" "seaborn>=0.13,<1" \
    "jupyter>=1.0,<2" "pyyaml>=6.0,<7" "toml>=0.10,<1"

# Create non-root verifier user
RUN useradd -m -s /bin/bash verifier
USER verifier
WORKDIR /workspace
