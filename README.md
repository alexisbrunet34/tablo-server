# Tablo OCR (POC)

API Python (FastAPI) qui reçoit une image et renvoie le texte manuscrit extrait.
Pipeline : **PaddleOCR** détecte les lignes de texte, puis **TrOCR handwritten** (Hugging Face) lit chacune d'elles.
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
(installation de PyTorch et PaddlePaddle, image de plusieurs Go). Au premier lancement, les
modèles sont téléchargés (internet requis ; TrOCR base ≈ 1,3 Go) et conservés dans des volumes Docker.
Pour un modèle plus léger/rapide, mettre `TROCR_MODEL: microsoft/trocr-small-handwritten`
dans `docker-compose.yml`.

Sans Compose :

```bash
docker build -t tablo-ocr .
docker run -d --name tablo-ocr -p 8000:8000 -e TROCR_MODEL=microsoft/trocr-base-handwritten --restart unless-stopped tablo-ocr
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

- TrOCR handwritten est entraîné sur de l'**anglais** (base IAM) : les accents français (é, è, à...) seront mal lus.
- Il lit une ligne à la fois : la qualité dépend de la détection des lignes par PaddleOCR (mise en page simple recommandée).
- Pas de score de confiance dans la réponse.
- Sur Pi 4, compter quelques secondes par image (CPU uniquement).
- Pas d'authentification, pas de HTTPS.

## Pistes d'amélioration

- **Français / accents** : fine-tuner TrOCR sur des données françaises, ou utiliser un modèle de vision (API Claude) en repli.
- **Prétraitement** : niveaux de gris, binarisation (OpenCV), redressement pour améliorer la lecture.
- **Performance** : utiliser `trocr-small-handwritten`, exporter en ONNX, quantifier le modèle ; file d'attente pour traiter une image à la fois.
- **Déploiement** : service `systemd` pour démarrer au boot, reverse proxy (nginx/Caddy) avec HTTPS.
- **Sécurité** : clé d'API ou token sur `/ocr`.
- **Qualité du code** : tests automatisés, Dockerfile (image arm64).
