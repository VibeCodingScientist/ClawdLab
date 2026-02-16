FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git make gcc g++ && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy scipy pandas scikit-learn matplotlib seaborn \
    jupyter pyyaml toml

# Create non-root verifier user
RUN useradd -m -s /bin/bash verifier
USER verifier
WORKDIR /workspace
