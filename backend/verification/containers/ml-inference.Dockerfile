FROM python:3.11-slim

RUN pip install --no-cache-dir \
    "torch>=2.1,<3" --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
    "transformers>=4.36,<5" "datasets>=2.16,<3" "accelerate>=0.25,<1" \
    "sentencepiece>=0.1.99,<1" "protobuf>=4.25,<5"

# Create non-root verifier user
RUN useradd -m -s /bin/bash verifier
USER verifier
WORKDIR /workspace
