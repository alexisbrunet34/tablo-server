"""API POC : reçoit une image, lit l'écriture manuscrite avec TrOCR et renvoie le texte.

Pipeline en 2 étapes :
  1. PaddleOCR (détection seule) trouve les zones de texte dans l'image ;
  2. TrOCR (Hugging Face) lit le manuscrit de chaque zone découpée.
TrOCR ne sait lire qu'UNE ligne de texte à la fois, d'où l'étape de détection.
"""
import io
import os

import numpy as np
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from paddleocr import PaddleOCR
from PIL import Image, ImageOps
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

# Modèle TrOCR : "microsoft/trocr-base-handwritten" (précis, ~1,3 Go) ou
# "microsoft/trocr-small-handwritten" (~250 Mo, plus rapide sur Pi, un peu moins précis).
TROCR_MODEL = os.getenv("TROCR_MODEL", "microsoft/trocr-base-handwritten")
# Taille max de l'image acceptée (5 Mo) pour ne pas saturer la mémoire du Pi.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Côté le plus long max (px) : les grandes photos sont réduites, sinon la détection est très lente.
MAX_SIDE = 1600
# Marge (px) ajoutée autour de chaque zone détectée pour ne pas couper les lettres.
CROP_PADDING = 6

app = FastAPI(title="Tablo OCR", description="Extraction de texte manuscrit via TrOCR")

# Les modèles sont chargés UNE seule fois au démarrage (le chargement prend du temps).
# Détecteur de zones de texte (la langue n'a pas d'importance pour la détection seule).
detector = PaddleOCR(lang="en", show_log=False)
processor = TrOCRProcessor.from_pretrained(TROCR_MODEL)
trocr = VisionEncoderDecoderModel.from_pretrained(TROCR_MODEL).eval()  # .eval() = mode inférence


def load_image(data: bytes) -> Image.Image:
    """Décode les octets reçus en image PIL RGB, orientée et redimensionnée si besoin."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")  # corrige la rotation des photos de téléphone
    except Exception:
        raise HTTPException(status_code=400, detail="Fichier image invalide")
    img.thumbnail((MAX_SIDE, MAX_SIDE))  # réduit en conservant les proportions
    return img


def detect_lines(img: Image.Image) -> list[tuple[int, int, int, int]]:
    """Détecte les zones de texte et les regroupe en lignes, dans l'ordre de lecture.

    Retourne une liste de rectangles (gauche, haut, droite, bas), un par ligne.
    """
    # On appelle directement le détecteur interne : detector.ocr(rec=False) plante dans
    # PaddleOCR 2.7.3 (bug sur la valeur de retour). PaddleOCR attend une image BGR (OpenCV).
    polygons, _ = detector.text_detector(np.array(img)[:, :, ::-1])
    boxes = []
    for polygon in [] if polygons is None else polygons:
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))

    # Regroupement : une zone appartient à la ligne courante si son centre vertical
    # est proche de celui de la ligne ; sinon on commence une nouvelle ligne.
    boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
    lines = []  # chaque ligne = liste de zones
    for box in boxes:
        center = (box[1] + box[3]) / 2
        if lines:
            last = lines[-1]
            last_center = sum((b[1] + b[3]) / 2 for b in last) / len(last)
            if abs(center - last_center) < (box[3] - box[1]) / 2:
                last.append(box)
                continue
        lines.append([box])

    # Fusionne les zones de chaque ligne en un seul rectangle (de gauche à droite).
    return [
        (
            int(min(b[0] for b in line)),
            int(min(b[1] for b in line)),
            int(max(b[2] for b in line)),
            int(max(b[3] for b in line)),
        )
        for line in lines
    ]


def read_line(line_img: Image.Image) -> str:
    """Lit le texte manuscrit d'une image de ligne avec TrOCR."""
    pixel_values = processor(images=line_img, return_tensors="pt").pixel_values
    with torch.no_grad():  # pas de calcul de gradients : plus rapide et moins de mémoire
        ids = trocr.generate(pixel_values, max_new_tokens=64)
    return processor.batch_decode(ids, skip_special_tokens=True)[0].strip()


@app.get("/health")
def health():
    """Vérifie que le serveur tourne."""
    return {"status": "ok"}


@app.post("/ocr")
def extract_text(file: UploadFile = File(...)):
    """Reçoit une image (champ multipart 'file') et renvoie le texte manuscrit détecté.

    Fonction synchrone (def et non async def) : FastAPI l'exécute dans un thread,
    ce qui évite de bloquer le serveur pendant le calcul.
    """
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image trop volumineuse (max 5 Mo)")

    img = load_image(data)
    lines = []
    for left, top, right, bottom in detect_lines(img):
        crop = img.crop((
            max(left - CROP_PADDING, 0), max(top - CROP_PADDING, 0),
            min(right + CROP_PADDING, img.width), min(bottom + CROP_PADDING, img.height),
        ))
        text = read_line(crop)
        if text:
            lines.append({"text": text})

    return {"text": "\n".join(l["text"] for l in lines), "lines": lines}
