FROM ubuntu:22.04
RUN apt-get update && apt-get install -y curl git build-essential && \
    curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | \
    sh -s -- -y --default-toolchain leanprover/lean4:v4.3.0
ENV PATH="/root/.elan/bin:$PATH"
RUN git clone --depth 1 https://github.com/leanprover-community/mathlib4.git /opt/mathlib4 && \
    cd /opt/mathlib4 && lake build
ENV MATHLIB_PATH="/opt/mathlib4"
WORKDIR /workspace
