#!/usr/bin/env bash
# ===========================================
# Build ClawdLab verification Docker images
# ===========================================
# Usage:
#   ./build.sh all            # Build all images
#   ./build.sh lean4          # Build Lean 4 + Mathlib image only
#   ./build.sh compbio        # Build CompBio image only
#   ./build.sh coq            # Build Coq + MathComp image
#   ./build.sh isabelle       # Build Isabelle/HOL image
#   ./build.sh reproducibility # Build reproducibility sandbox
#   ./build.sh ml-inference   # Build ML inference image

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

build_lean4() {
    echo "==> Building clawdlab/lean4-mathlib ..."
    docker build \
        -f "$SCRIPT_DIR/lean4-mathlib.Dockerfile" \
        -t clawdlab/lean4-mathlib:latest \
        "$SCRIPT_DIR"
    echo "==> clawdlab/lean4-mathlib:latest built successfully"
}

build_compbio() {
    echo "==> Building clawdlab/compbio-cpu ..."
    docker build \
        -f "$SCRIPT_DIR/compbio.Dockerfile" \
        -t clawdlab/compbio-cpu:latest \
        "$SCRIPT_DIR"
    echo "==> clawdlab/compbio-cpu:latest built successfully"
}

build_coq() {
    echo "==> Building clawdlab/coq ..."
    docker build \
        -f "$SCRIPT_DIR/coq.Dockerfile" \
        -t clawdlab/coq:latest \
        "$SCRIPT_DIR"
    echo "==> clawdlab/coq:latest built successfully"
}

build_isabelle() {
    echo "==> Building clawdlab/isabelle ..."
    docker build \
        -f "$SCRIPT_DIR/isabelle.Dockerfile" \
        -t clawdlab/isabelle:latest \
        "$SCRIPT_DIR"
    echo "==> clawdlab/isabelle:latest built successfully"
}

build_reproducibility() {
    echo "==> Building clawdlab/reproducibility ..."
    docker build \
        -f "$SCRIPT_DIR/reproducibility.Dockerfile" \
        -t clawdlab/reproducibility:latest \
        "$SCRIPT_DIR"
    echo "==> clawdlab/reproducibility:latest built successfully"
}

build_ml_inference() {
    echo "==> Building clawdlab/ml-inference ..."
    docker build \
        -f "$SCRIPT_DIR/ml-inference.Dockerfile" \
        -t clawdlab/ml-inference:latest \
        "$SCRIPT_DIR"
    echo "==> clawdlab/ml-inference:latest built successfully"
}

case "${1:-all}" in
    lean4)
        build_lean4
        ;;
    compbio)
        build_compbio
        ;;
    coq)
        build_coq
        ;;
    isabelle)
        build_isabelle
        ;;
    reproducibility)
        build_reproducibility
        ;;
    ml-inference)
        build_ml_inference
        ;;
    all)
        build_compbio
        build_lean4
        build_coq
        build_isabelle
        build_reproducibility
        build_ml_inference
        ;;
    *)
        echo "Usage: $0 [lean4|compbio|coq|isabelle|reproducibility|ml-inference|all]"
        exit 1
        ;;
esac

echo "Done."
