# CAMPFLOW V1

Application Dash pour Camping La Peyrugue : pointage saisonniers par code QR, demandes manuelles en cas d'oubli, validation responsable hebdomadaire et export Excel.

## Installation

```bash
cd /Users/leclercqa1234/campflow-v1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Configuration optionnelle :

```bash
export CAMPFLOW_BASE_URL="http://127.0.0.1:8050"
```

Application locale :

- Accueil : http://127.0.0.1:8050
- QR restaurant : http://127.0.0.1:8050/pointage/restaurant
- QR ménage : http://127.0.0.1:8050/pointage/menage
- QR entretien : http://127.0.0.1:8050/pointage/entretien
- Responsable : http://127.0.0.1:8050/manager

## Interface saisonnier

Les codes QR imprimés et plastifiés doivent pointer vers les adresses de service :

- `/pointage/restaurant`
- `/pointage/menage`
- `/pointage/entretien`

La page saisonnier est mobile first. Elle affiche un seul gros bouton :

- `Commencer mon service` si aucun créneau QR n'est ouvert
- `Terminer mon service` si un créneau QR est déjà ouvert

Un créneau ouvert correspond à une ligne `work_sessions` avec `start_time` renseigné et `end_time` vide.

## Espace responsable

L'espace responsable est disponible sur :

```text
http://127.0.0.1:8050/manager
```

Compte responsable créé automatiquement si aucun utilisateur n'existe :

```text
email : admin@campflow.local
mot de passe temporaire : manager
```

Après connexion, allez dans `Paramètres employés` pour créer un responsable établissement ou changer un mot de passe.
Le compte par défaut doit changer son mot de passe à la première connexion. Les sessions responsables expirent après 8 heures.

## Journal d'activité

Les actions sensibles réalisées par un responsable sont enregistrées dans `audit_logs` avec l'utilisateur connecté, l'établissement, l'élément concerné, l'ancienne valeur, la nouvelle valeur, le commentaire et l'horodatage.

Depuis `/manager/parametres`, la section `Journal d’activité` affiche les 50 dernières actions. L'export Excel ajoute aussi un onglet `Journal activité`.

## Base de données

La base SQLite est créée automatiquement au lancement :

```text
data/campflow.sqlite3
```

Le schéma source est dans :

```text
database/schema.sql
```

### Modèle multi-établissement

CAMPFLOW prépare désormais les données pour plusieurs établissements.
Au démarrage, l'application crée automatiquement l'établissement par défaut :

```text
Camping La Peyrugue
slug: la-peyrugue
id: 1
```

Les tables métier portent un `establishment_id` :

- `employees`
- `services`
- `punches`
- `work_sessions`
- `manual_time_requests`
- `validation_logs`

Lors d'une migration depuis la V1, les lignes existantes sont automatiquement rattachées à `Camping La Peyrugue`. L'interface actuelle continue d'utiliser cet établissement par défaut tant qu'il n'y a pas de comptes manager multi-établissements.

## Générer les codes QR

```bash
cd /Users/leclercqa1234/campflow-v1
python3 scripts/generate_qr_codes.py
```

Les fichiers générés sont :

- PNG : `exports/qr_codes/campflow_restaurant.png`
- PNG : `exports/qr_codes/campflow_menage.png`
- PNG : `exports/qr_codes/campflow_entretien.png`
- HTML imprimable : `exports/campflow_qr_codes_printable.html`

Depuis l'espace responsable, la section `Codes QR imprimables` permet aussi de définir l'adresse de base, générer les fichiers et afficher un aperçu.

## Imprimer les codes QR

Ouvrez `exports/campflow_qr_codes_printable.html` dans un navigateur, puis imprimez.

Paramètres conseillés :

- format A4
- impression à 100 %
- marges par défaut ou aucune marge selon l'imprimante
- 1 page par service

## Export Excel

Depuis l'espace responsable, cliquez sur `Exporter la semaine en Excel`.

Le navigateur télécharge directement un fichier au format :

```text
campflow_export_semaine_AAAA-MM-JJ.xlsx
```

Une copie est aussi conservée dans `exports/`.

## Publication

La V1 se lance en production avec Gunicorn :

```bash
gunicorn app:server --bind 0.0.0.0:$PORT
```

Variables à définir :

```bash
export CAMPFLOW_BASE_URL="https://votre-domaine.fr"
```

Changez le mot de passe temporaire du compte `admin@campflow.local` dès le premier lancement en production.

Important : `data/` et `exports/` doivent être persistants en production. Voir `DEPLOYMENT.md`.
