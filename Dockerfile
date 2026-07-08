# Backend image for CAD Intelligence (FastAPI + Meshy + CadQuery/OpenCASCADE).
# Railway/Render/Fly use this instead of guessing the build. Python 3.11 because
# CadQuery's OCP (OpenCASCADE) wheels are most reliable there.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System libraries required at runtime by:
#  - opencv-python  -> libgl1, libglib2.0-0
#  - cadquery / OCP -> OpenGL + X11 stack (libglu, libsm, libxext, libxrender, ...)
#  - scipy/onnxruntime OpenMP -> libgomp1
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 \
      libglu1-mesa \
      libglib2.0-0 \
      libsm6 \
      libxext6 \
      libxrender1 \
      libx11-6 \
      libxi6 \
      libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching. (birefnet/torch extras in
# requirements-birefnet.txt are intentionally omitted — rembg is the default and
# torch would roughly triple the image size.)
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code (frontend + local state are excluded via .dockerignore).
COPY . .

# Hosts inject $PORT; default to 8080 (Railway's routed port) if unset.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
