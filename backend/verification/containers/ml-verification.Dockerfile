FROM nvidia/cuda:12.1-devel-ubuntu22.04
RUN apt-get update && apt-get install -y python3.11 python3-pip git && \
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
    pip3 install lm-eval transformers datasets evaluate accelerate && \
    pip3 install wandb mlflow
ENV CUDA_VISIBLE_DEVICES=0
WORKDIR /workspace
