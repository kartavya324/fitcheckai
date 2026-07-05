FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

# System dependencies
RUN apt-get update && apt-get install -y \
    git wget curl build-essential \
    libgl1-mesa-glx libglib2.0-0 \
    libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip install --no-cache-dir \
    runpod \
    torch torchvision \
    numpy opencv-python \
    trimesh \
    pymeshlab \
    huggingface_hub \
    diffusers \
    transformers \
    accelerate

# Clone ECON
RUN git clone https://github.com/YuliangXiu/ECON.git /workspace/ECON
WORKDIR /workspace/ECON
RUN pip install --no-cache-dir -r requirements.txt

# Clone TeCH  
RUN git clone https://github.com/huangyangyi/TeCH.git /workspace/TeCH
WORKDIR /workspace/TeCH
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /workspace

# Copy handler
COPY handler.py /workspace/handler.py

# Create model cache dirs
RUN mkdir -p /workspace/models/econ /workspace/models/tech

CMD ["python", "-u", "handler.py"]
