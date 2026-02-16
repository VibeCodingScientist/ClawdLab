FROM coqorg/coq:8.18

# Install MathComp
RUN opam install -y coq-mathcomp-ssreflect coq-mathcomp-algebra

# Create non-root verifier user
RUN useradd -m -s /bin/bash verifier
USER verifier
WORKDIR /workspace
