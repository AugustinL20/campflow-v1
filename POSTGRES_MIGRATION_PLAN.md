# Plan de migration SQLite → PostgreSQL

## Pourquoi SQLite est risqué en production

SQLite utilise des locks fichier pour gérer la concurrence. Sous Gunicorn avec plusieurs workers (ou simplement avec plusieurs utilisateurs actifs simultanément), les écritures concurrentes provoquent des erreurs `database is locked` ou, pire, des corruptions silencieuses.

Problèmes concrets avec CAMPFLOW :
- Un saisonnier qui scanne un QR pendant qu'un responsable valide un créneau = conflit d'écriture possible
- Le filesystem Render est **éphémère** : toutes les données (SQLite, exports, backups) disparaissent à chaque redéploiement si aucun volume persistant n'est configuré
- Impossible de faire des sauvegardes automatiques fiables depuis Render
- Impossible de scaler horizontalement (plusieurs instances) avec un fichier SQLite partagé

## Pourquoi PostgreSQL sur Render

- Render propose PostgreSQL managé nativement (free tier disponible)
- Données persistantes indépendantes du filesystem du service web
- Connexions concurrentes gérées correctement
- Fondation pour le multi-tenant avec Row Level Security (RLS)
- Compatible avec le code Flask/SQLAlchemy existant avec un changement minimal

## Étapes de migration

### Étape 1 — Préparer l'environnement (30 min)

1. Créer une instance PostgreSQL sur Render (Dashboard → New → PostgreSQL)
2. Récupérer la `DATABASE_URL` fournie par Render (format : `postgresql://user:password@host/dbname`)
3. Ajouter `DATABASE_URL` comme variable d'environnement dans le service web Render
4. Installer le driver : ajouter `psycopg2-binary==2.9.9` dans `requirements.txt`

### Étape 2 — Adapter `database/db.py` (2-3h)

Remplacer la connexion SQLite par psycopg2 ou SQLAlchemy.

Option A — psycopg2 direct (changement minimal) :
```python
import os
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ["DATABASE_URL"]

@contextmanager
def get_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

Points d'attention :
- SQLite utilise `?` comme placeholder, PostgreSQL utilise `%s`
- Toutes les requêtes dans `queries.py`, `auth.py`, `audit.py` doivent être mises à jour
- SQLite `sqlite3.Row` (accès par nom de colonne) → psycopg2 `RealDictCursor` (même comportement)
- `AUTOINCREMENT` SQLite → `SERIAL` ou `GENERATED ALWAYS AS IDENTITY` PostgreSQL
- `INTEGER DEFAULT CURRENT_TIMESTAMP` → `TIMESTAMP DEFAULT NOW()`
- `executescript` n'existe pas en psycopg2 → utiliser des requêtes séparées pour le schéma

Option B — SQLAlchemy (recommandé pour la V2) :
Ajouter `sqlalchemy==2.0.x` + `alembic` pour les migrations de schéma. Permet de basculer entre SQLite (dev) et PostgreSQL (prod) via la `DATABASE_URL`.

### Étape 3 — Adapter le schéma SQL (1h)

Fichier `database/schema.sql` à adapter pour PostgreSQL :

```sql
-- SQLite                              → PostgreSQL
INTEGER PRIMARY KEY AUTOINCREMENT      → SERIAL PRIMARY KEY
TEXT DEFAULT CURRENT_TIMESTAMP         → TEXT DEFAULT NOW()
PRAGMA foreign_keys = ON               → (géré par défaut dans Postgres)
INSERT OR IGNORE                       → INSERT ... ON CONFLICT DO NOTHING
```

### Étape 4 — Migrer les données existantes (1-2h)

```bash
# Exporter la base SQLite actuelle
python scripts/export_sqlite_to_csv.py  # à créer : exporte chaque table en CSV

# Importer dans PostgreSQL
psql $DATABASE_URL < schema_postgres.sql
psql $DATABASE_URL < data_import.sql    # ou via COPY FROM CSV
```

Alternative : utiliser `pgloader` (outil open source qui migre directement SQLite → PostgreSQL).

### Étape 5 — Tests (1h)

- [ ] Connexion PostgreSQL depuis l'app locale avec `DATABASE_URL` pointant sur Render
- [ ] `init_db()` crée les tables sans erreur
- [ ] Login responsable fonctionne
- [ ] Pointage QR fonctionne
- [ ] Export Excel fonctionne
- [ ] Validation de créneaux fonctionne
- [ ] Audit logs écrits correctement

### Étape 6 — Déploiement

1. Pousser le code sur GitHub
2. Render redéploie automatiquement
3. Vérifier les logs de démarrage (`init_db()`)
4. Tester le login depuis l'URL publique
5. Tester un scan QR depuis un téléphone

## Tables concernées

Toutes les tables sont à migrer :
- `establishments`
- `users`
- `employees`
- `services`
- `punches`
- `work_sessions`
- `manual_time_requests`
- `validation_logs`
- `audit_logs`

## Risques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Perte de données en migration | Moyen | Critique | Backup SQLite complet avant migration |
| Différences de types SQLite/Postgres | Élevé | Moyen | Tester en staging avant prod |
| Placeholders `?` non remplacés | Élevé | Bloquant | Grep systématique de `?` dans queries.py |
| `INSERT OR IGNORE` non supporté | Élevé | Moyen | Remplacer par `ON CONFLICT DO NOTHING` |
| Connexion pool saturé | Faible | Moyen | Configurer `pool_size` SQLAlchemy |

## Variables d'environnement à configurer sur Render

```
DATABASE_URL=postgresql://...  # fourni par Render PostgreSQL
CAMPFLOW_SECRET_KEY=<clé aléatoire forte>
CAMPFLOW_BASE_URL=https://campflow-v1.onrender.com
```

## Ordre recommandé

1. D'abord : migrer les données (data-only, garder SQLite en code)
2. Ensuite : adapter `db.py` et `schema.sql` pour PostgreSQL
3. Ensuite : mettre à jour toutes les requêtes (placeholders `%s`)
4. Ensuite : tests complets en local avec PostgreSQL (Docker ou service Render)
5. Enfin : déploiement sur Render avec rollback SQLite prêt

**Durée estimée totale : 1 journée de développement pour un développeur familier avec le code.**
