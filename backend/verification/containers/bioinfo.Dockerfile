FROM python:3.11-slim
RUN apt-get update && apt-get install -y default-jre git curl && \
    curl -s https://get.nextflow.io | bash && mv nextflow /usr/local/bin/ && \
    pip install snakemake biopython pysam pandas scipy && \
    pip install pydeseq2
WORKDIR /workspace
