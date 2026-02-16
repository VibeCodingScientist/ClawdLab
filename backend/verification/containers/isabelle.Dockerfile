FROM makarius/isabelle:Isabelle2024

# Pre-build HOL session for faster proofs
RUN isabelle build -b HOL

# Create non-root verifier user
USER root
RUN useradd -m -s /bin/bash verifier && \
    chown -R verifier:verifier /home/verifier
USER verifier
WORKDIR /workspace
