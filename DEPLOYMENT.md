# Publier CAMPFLOW V1

CAMPFLOW V1 est une application Dash/Flask. En production, lancez-la avec Gunicorn, pas avec `python3 app.py`.

## Variables obligatoires

```bash
CAMPFLOW_BASE_URL=https://votre-domaine.fr
```

`CAMPFLOW_BASE_URL` sert aux liens et codes QR. Après changement du domaine, régénérez les codes QR depuis `/manager/qrcodes`.

Si aucun utilisateur n'existe, CAMPFLOW crée au premier démarrage :

```text
email : admin@campflow.local
mot de passe temporaire : manager
```

Changez ce mot de passe dès la première connexion en production.
L'application force ce changement avant d'autoriser l'accès à l'espace responsable. Une session responsable expire après 8 heures.

## Données persistantes

La V1 utilise SQLite et écrit des exports locaux.

À conserver entre les redémarrages :

```text
data/
exports/
```

Sur Render, Railway, Fly.io ou Docker, configurez un volume persistant monté sur ces dossiers. Sans volume, les pointages peuvent être perdus lors d'un redéploiement.

## Commande de démarrage

```bash
gunicorn app:server --bind 0.0.0.0:$PORT
```

En local, vous pouvez tester la commande avec :

```bash
PORT=8050 gunicorn app:server --bind 0.0.0.0:$PORT
```

## Déploiement PaaS

Les plateformes type Render ou Railway peuvent utiliser le `Procfile` :

```text
web: gunicorn app:server --bind 0.0.0.0:${PORT:-8050}
```

À configurer dans la plateforme :

- variable `CAMPFLOW_BASE_URL`
- volume persistant pour `data/`
- volume persistant pour `exports/` si vous voulez conserver les fichiers générés

## Déploiement Docker

Build :

```bash
docker build -t campflow-v1 .
```

Run :

```bash
docker run --rm \
  -p 8050:8050 \
  -e PORT=8050 \
  -e CAMPFLOW_BASE_URL=http://localhost:8050 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/exports:/app/exports" \
  campflow-v1
```

## Liste de contrôle avant impression des codes QR

- `/manager` accessible en HTTPS
- mot de passe temporaire du compte `admin@campflow.local` changé
- pointage testé sur mobile
- export Excel téléchargé depuis le navigateur
- CSV pour tableur Google généré
- codes QR régénérés avec le vrai domaine
- sauvegarde de `data/campflow.sqlite3` planifiée
