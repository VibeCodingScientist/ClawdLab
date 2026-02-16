FROM coqorg/coq:8.18

# Install MathComp
RUN opam install -y coq-mathcomp-ssreflect.2.2.0 coq-mathcomp-algebra.2.2.0

# Create non-root verifier user
RUN useradd -m -s /bin/bash verifier
USER verifier
WORKDIR /workspace
