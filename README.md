# Tablo OCR (POC)

API Python (FastAPI + PaddleOCR) qui reçoit une image et renvoie le texte extrait.
Pensée pour un Raspberry Pi 4 sous Ubuntu 64 bits (aarch64).

## Lancement avec Docker (recommandé)

Prérequis : Docker et le plugin Compose sur le Raspberry Pi
(`sudo apt install -y docker.io docker-compose-v2`).

```bash
# Construire l'image et démarrer le serveur en arrière-plan
docker compose up -d --build

# Voir les logs / arrêter
docker compose logs -f
docker compose down
```

Le serveur écoute sur le port 8000. La première construction est longue sur un Pi
(installation de PaddlePaddle). Au premier lancement, PaddleOCR télécharge ses modèles
(~15 Mo, internet requis) ; ils sont conservés dans un volume Docker.
Pour changer la langue, modifier `OCR_LANG` dans `docker-compose.yml` (ex. `en`).

Sans Compose :

```bash
docker build -t tablo-ocr .
docker run -d --name tablo-ocr -p 8000:8000 -e OCR_LANG=fr --restart unless-stopped tablo-ocr
```

## Lancement sans Docker

```bash
sudo apt update && sudo apt install -y python3-venv libgl1 libglib2.0-0
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Documentation interactive : http://localhost:8000/docs

## Envoyer une image avec curl

Le fichier est envoyé en `multipart/form-data` dans le champ `file` (JPEG, PNG... max 5 Mo) :

```bash
curl -X POST -F "file=@/chemin/vers/mon_image.jpg" http://<ip-du-pi>:8000/ocr
```

Le `@` devant le chemin est obligatoire : sans lui, curl envoie le texte du chemin et non le fichier.

Depuis Windows (PowerShell), utiliser `curl.exe` (et non `curl`, qui est un alias d'une autre commande) :

```powershell
curl.exe -X POST -F "file=@C:\Users\alexis\Desktop\image.jpg" http://<ip-du-pi>:8000/ocr
```

`localhost` ne fonctionne que si la commande est lancée sur la machine qui héberge le serveur ; depuis un autre poste, utiliser l'IP du Pi.
Vérifier que le serveur répond : `curl http://<ip-du-pi>:8000/health`.

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
