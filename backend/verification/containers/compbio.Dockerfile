FROM nvidia/cuda:12.1-devel-ubuntu22.04
RUN apt-get update && apt-get install -y python3.11 python3-pip git && \
    pip3 install torch --index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install fair-esm biopython tmtools && \
    pip3 install colabfold[alphafold] || true
# Pre-download ESMFold weights
RUN python3 -c "from esm.pretrained import esmfold_v1; esmfold_v1()" || true
WORKDIR /workspace
