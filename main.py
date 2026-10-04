"""API POC : reçoit une image, extrait le texte avec PaddleOCR et le renvoie."""
import io
import os

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from paddleocr import PaddleOCR
from PIL import Image, ImageOps

# Langue du modèle OCR (ex: "fr", "en"), configurable via variable d'environnement.
OCR_LANG = os.getenv("OCR_LANG", "fr")
# Taille max de l'image acceptée (5 Mo) pour ne pas saturer la mémoire du Pi.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Côté le plus long max (px) : les grandes photos sont réduites, sinon l'OCR est très lent.
MAX_SIDE = 1600

app = FastAPI(title="Tablo OCR", description="Extraction de texte manuscrit via PaddleOCR")

# Le modèle est chargé UNE seule fois au démarrage (le chargement prend plusieurs secondes).
ocr = PaddleOCR(use_angle_cls=True, lang=OCR_LANG, show_log=False)


def load_image(data: bytes) -> np.ndarray:
    """Décode les octets reçus en tableau numpy RGB, orienté et redimensionné si besoin."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")  # corrige la rotation des photos de téléphone
    except Exception:
        raise HTTPException(status_code=400, detail="Fichier image invalide")
    img.thumbnail((MAX_SIDE, MAX_SIDE))  # réduit en conservant les proportions
    return np.array(img)


@app.get("/health")
def health():
    """Vérifie que le serveur tourne."""
    return {"status": "ok"}


@app.post("/ocr")
def extract_text(file: UploadFile = File(...)):
    """Reçoit une image (champ multipart 'file') et renvoie le texte détecté.

    Fonction synchrone (def et non async def) : FastAPI l'exécute dans un thread,
    ce qui évite de bloquer le serveur pendant le calcul OCR.
    """
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image trop volumineuse (max 5 Mo)")

    result = ocr.ocr(load_image(data), cls=True)

    # result[0] est None si rien n'est détecté, sinon une liste de [boîte, (texte, confiance)].
    lines = []
    for box, (text, confidence) in result[0] or []:
        lines.append({"text": text, "confidence": round(float(confidence), 3)})

    return {"text": "\n".join(l["text"] for l in lines), "lines": lines}
