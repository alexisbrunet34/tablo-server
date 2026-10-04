# Tablo OCR (POC)

API Python (FastAPI + PaddleOCR) qui reçoit une image et renvoie le texte extrait.
Pensée pour un Raspberry Pi 4 sous Ubuntu 64 bits (aarch64).

## Installation

```bash
sudo apt update && sudo apt install -y python3-venv libgl1 libglib2.0-0
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

> Au premier lancement, PaddleOCR télécharge ses modèles (~15 Mo), une connexion internet est nécessaire.

## Lancement

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Variable optionnelle : `OCR_LANG` (défaut `fr`, ex. `OCR_LANG=en`).
Documentation interactive : http://localhost:8000/docs

## Utilisation

```bash
curl -F "file=@mon_image.jpg" http://<ip-du-pi>:8000/ocr
```

Réponse :

```json
{
  "text": "Bonjour\nle monde",
  "lines": [
    {"text": "Bonjour", "confidence": 0.93},
    {"text": "le monde", "confidence": 0.88}
  ]
}
```

Autres endpoints : `GET /health`.

## Limites du POC

- PaddleOCR n'est **pas spécialisé dans le manuscrit** : bon sur une écriture claire en script/capitales, moyen sur de l'écriture cursive.
- Sur Pi 4, compter quelques secondes par image (CPU uniquement).
- Pas d'authentification, pas de HTTPS.

## Pistes d'amélioration

- **Qualité manuscrit** : tester un modèle dédié (TrOCR handwritten de Hugging Face, ou l'API Claude/vision) en repli quand la confiance est basse.
- **Prétraitement** : niveaux de gris, binarisation (OpenCV), redressement pour améliorer la lecture.
- **Performance** : exporter en ONNX / utiliser les modèles « mobile » de PaddleOCR ; file d'attente pour traiter une image à la fois.
- **Déploiement** : service `systemd` pour démarrer au boot, reverse proxy (nginx/Caddy) avec HTTPS.
- **Sécurité** : clé d'API ou token sur `/ocr`.
- **Qualité du code** : tests automatisés, Dockerfile (image arm64).
