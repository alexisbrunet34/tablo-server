# Tablo OCR (POC)

API Python (FastAPI) qui reçoit une image et renvoie le texte manuscrit qu'elle contient.
La lecture est faite par un **modèle de vision local** (Qwen2.5-VL, via Hugging Face Transformers) :
aucune donnée ne quitte la machine.

## Prérequis matériels

Le modèle est lourd : ce n'est **pas adapté à un Raspberry Pi**.

| Modèle (`VISION_MODEL`)        | Mémoire nécessaire | Remarque                          |
|--------------------------------|--------------------|-----------------------------------|
| `Qwen/Qwen2.5-VL-3B-Instruct`  | ~8 Go VRAM ou ~8 Go RAM | défaut, bon compromis        |
| `Qwen/Qwen2.5-VL-7B-Instruct`  | ~16 Go VRAM        | plus précis, licence Apache 2.0   |

- Avec un **GPU NVIDIA** : quelques secondes par image.
- Sur **CPU seul** : fonctionne, mais compter de une à plusieurs minutes par image.

## Lancement avec Docker (recommandé)

Prérequis : Docker et le plugin Compose.

```bash
# Construire l'image et démarrer le serveur en arrière-plan
docker compose up -d --build

# Voir les logs / arrêter
docker compose logs -f
docker compose down
```

Le serveur écoute sur le port 8000. Au premier lancement, le modèle est téléchargé
(plusieurs Go, internet requis) et conservé dans un volume Docker : le démarrage prend du temps,
attendre la ligne `Application startup complete` dans les logs.

**GPU NVIDIA** : la configuration par défaut utilise le GPU (PyTorch CUDA 12.1 + accès GPU dans `docker-compose.yml`).
- Windows (Docker Desktop + WSL2) : il suffit d'avoir un pilote NVIDIA à jour sur Windows.
- Linux : installer le [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/).
- Vérifier : `curl http://localhost:8000/health` doit répondre `"device": "cuda"`.
- Pour utiliser le CPU à la place : mettre `TORCH_INDEX: https://download.pytorch.org/whl/cpu` et commenter le bloc `deploy`.

**Le conteneur redémarre en boucle pendant le chargement ?** C'est un manque de mémoire. Vérifier avec
`docker inspect <conteneur> --format "{{.State.OOMKilled}}"` (`true` = mémoire insuffisante), puis, sous Windows,
augmenter la mémoire de WSL2 dans `C:\Users\<vous>\.wslconfig` (`[wsl2]` puis `memory=12GB`) et lancer `wsl --shutdown`.

## Lancement sans Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install torch==2.5.1   # ou, pour la version CPU légère : pip install torch==2.5.1 --extra-index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Documentation interactive : http://localhost:8000/docs

## Configuration (variables d'environnement)

- `VISION_MODEL` : modèle Hugging Face à utiliser (défaut `Qwen/Qwen2.5-VL-3B-Instruct`).
- `OCR_PROMPT` : consigne donnée au modèle (par défaut : transcrire fidèlement le texte, en français).

## Envoyer une image avec curl

Le fichier est envoyé en `multipart/form-data` dans le champ `file` (JPEG, PNG... max 10 Mo) :

```bash
curl -X POST -F "file=@/chemin/vers/mon_image.jpg" http://localhost:8000/ocr
```

Le `@` devant le chemin est obligatoire : sans lui, curl envoie le texte du chemin et non le fichier.

Depuis Windows (PowerShell), utiliser `curl.exe` (et non `curl`, qui est un alias d'une autre commande) :

```powershell
curl.exe -X POST -F "file=@C:\Users\alexis\Desktop\image.jpg" http://localhost:8000/ocr
```

Si la commande est lancée depuis un autre poste, remplacer `localhost` par l'IP du serveur.
Vérifier que le serveur répond : `curl http://localhost:8000/health`.

Réponse :

```json
{
  "text": "Bonjour\nle monde",
  "lines": [
    {"text": "Bonjour"},
    {"text": "le monde"}
  ]
}
```

## Limites du POC

- Un modèle génératif peut **inventer ou « corriger » des mots** plutôt que de les lire fidèlement.
- Pas de score de confiance dans la réponse.
- Sous Docker Desktop (Windows), la mémoire allouée à WSL2 doit être suffisante (voir ci-dessous).
- Une seule requête à la fois est vraiment efficace (le modèle occupe toute la machine).
- Pas d'authentification, pas de HTTPS.

## Pistes d'amélioration

- **Qualité** : passer à `Qwen2.5-VL-7B`, ajuster `OCR_PROMPT` (ex. préciser la langue ou le type d'écriture).
- **Performance** : quantification (4/8 bits), ou serveur d'inférence dédié (vLLM, llama.cpp).
- **Déploiement** : reverse proxy avec HTTPS, clé d'API sur `/ocr`.
- **Qualité du code** : tests automatisés avec un jeu d'images de référence.
