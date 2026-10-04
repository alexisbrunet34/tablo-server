# Image Python officielle
FROM python:3.10-slim

WORKDIR /app

# PyTorch : version CPU par défaut (légère). Pour un GPU NVIDIA, construire avec
#   --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir torch==2.5.1 --index-url ${TORCH_INDEX}

# Les dépendances d'abord : cette couche est mise en cache tant que requirements.txt ne change pas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
