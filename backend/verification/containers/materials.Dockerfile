FROM python:3.11-slim
RUN pip install pymatgen ase mace-torch chgnet matgl && \
    pip install mp-api
WORKDIR /workspace
