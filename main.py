"""API POC : reçoit une image, lit le texte manuscrit avec un modèle de vision local et le renvoie.

Le modèle (par défaut Qwen2.5-VL) regarde l'image entière et la transcrit, comme le ferait
un humain : plus besoin de détecter les lignes ni de gérer les accents à part.
"""
import io
import os

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, ImageOps
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

# Modèle de vision (Hugging Face). Exemples :
#   "Qwen/Qwen2.5-VL-3B-Instruct" : léger (~7 Go), bon compromis (défaut)
#   "Qwen/Qwen2.5-VL-7B-Instruct" : plus précis (~16 Go), licence Apache 2.0
MODEL_NAME = os.getenv("VISION_MODEL", "Qwen/Qwen2.5-VL-3B-Instruct")
# Consigne donnée au modèle : on lui demande de transcrire, sans commentaire.
PROMPT = os.getenv(
    "OCR_PROMPT",
    "Transcris fidèlement tout le texte manuscrit de cette image, en conservant les accents "
    "et les retours à la ligne. Réponds uniquement avec le texte, sans commentaire.",
)
# Taille max de l'image acceptée (10 Mo).
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Nombre max de pixels analysés : limite la mémoire et le temps de calcul (1 "jeton" = 28x28 px).
MAX_PIXELS = 1280 * 28 * 28
# Nombre max de jetons générés (assez pour une page de texte).
MAX_NEW_TOKENS = 512

app = FastAPI(title="Tablo OCR", description="Extraction de texte manuscrit via un modèle de vision local")

# Le modèle est chargé UNE seule fois au démarrage (cela prend du temps et beaucoup de RAM).
# GPU NVIDIA si disponible (rapide), sinon CPU (lent). bfloat16 divise par deux la mémoire
# utilisée par rapport à float32 (~7 Go au lieu de ~14 Go pour le modèle 3B).
device = "cuda" if torch.cuda.is_available() else "cpu"
processor = AutoProcessor.from_pretrained(MODEL_NAME, max_pixels=MAX_PIXELS, use_fast=False)
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL_NAME, torch_dtype=torch.bfloat16)
model = model.to(device).eval()


def load_image(data: bytes) -> Image.Image:
    """Décode les octets reçus en image PIL RGB, correctement orientée."""
    try:
        img = Image.open(io.BytesIO(data))
        return ImageOps.exif_transpose(img).convert("RGB")  # corrige la rotation des photos de téléphone
    except Exception:
        raise HTTPException(status_code=400, detail="Fichier image invalide")


def transcribe(img: Image.Image) -> str:
    """Demande au modèle de transcrire le texte de l'image."""
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[img], return_tensors="pt").to(device)

    with torch.no_grad():  # pas de calcul de gradients : plus rapide et moins de mémoire
        output = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)

    # On retire du résultat la partie "prompt" pour ne garder que la réponse générée.
    answer = output[:, inputs.input_ids.shape[1]:]
    return processor.batch_decode(answer, skip_special_tokens=True)[0].strip()


@app.get("/health")
def health():
    """Vérifie que le serveur tourne."""
    return {"status": "ok", "model": MODEL_NAME, "device": device}


@app.post("/ocr")
def extract_text(file: UploadFile = File(...)):
    """Reçoit une image (champ multipart 'file') et renvoie le texte manuscrit lu.

    Fonction synchrone (def et non async def) : FastAPI l'exécute dans un thread,
    ce qui évite de bloquer le serveur pendant le calcul.
    """
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image trop volumineuse (max 10 Mo)")

    text = transcribe(load_image(data))
    return {"text": text, "lines": [{"text": l} for l in text.splitlines() if l.strip()]}
