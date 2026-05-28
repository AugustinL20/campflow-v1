# CAMPFLOW V1 - Technical Audit

Date: 2026-05-28

## Synthese

CAMPFLOW V1 est une application Dash/Flask simple et lisible. La logique metier est concentree dans `database/queries.py`, les vues dans `pages/`, et les exports/QR dans `utils/`. Le niveau actuel est acceptable pour une V1 terrain pilote si Render dispose d'un disque persistant et si le volume d'utilisation reste faible a modere.

Le risque principal reste la persistance des donnees SQLite sur Render. Le deuxieme risque est la concentration de beaucoup de callbacks et de logique responsable dans `pages/manager.py`, qui augmente le risque de regression lors des evolutions. Le troisieme risque est l'absence de vraie suite de tests automatises.

## Problemes trouves

| Gravite | Zone | Probleme | Statut |
| --- | --- | --- | --- |
| Critique | Donnees | SQLite, exports et backups sont locaux. Sans Render Disk, un redeploiement peut perdre la base et les fichiers generes. | Non corrige par code, plan documente |
| Haute | QR | Les anciens QR etaient des liens publics persistants. Un token signe existait deja partiellement, mais sans `issued_at` et sans route query string. | Corrige |
| Haute | Login | Le rate-limit login bloquait aussi les bons mots de passe apres plusieurs echecs. | Corrige |
| Haute | Session | L'app depend de Flask session et d'un store Dash miroir. Un token signe de restauration existe pour stabiliser les callbacks manager. | Deja en place |
| Moyenne | Render | Docker ne creait pas tous les dossiers runtime et ne reprenait pas les options Gunicorn du Procfile. | Corrige |
| Moyenne | PostgreSQL | Les requetes utilisent SQLite, `?`, `PRAGMA`, `AUTOINCREMENT`, `sqlite3.Row`, pandas SQL direct. | Non migre, checklist creee |
| Moyenne | UX mobile | Interface saisonnier lisible, mais depend de Dash et du cold start Render. Feedback apres scan present. | Partiellement corrige |
| Moyenne | Manager | `pages/manager.py` est tres long et melange rendu, auth, actions et exports. | Non refactorise |
| Moyenne | Tests | Pas de tests automatises end-to-end ni tests de callbacks Dash. | Non corrige |
| Basse | Docs | Les docs mentionnaient encore les anciens chemins `/pointage/<slug>` comme flux principal. | Corrige partiellement |

## Architecture

- `app.py` initialise DB, auth par defaut, Dash, Flask server, cookies et routage global.
- `pages/pointage.py` gere l'interface saisonnier mobile.
- `pages/manager.py` gere login, changement mot de passe, navigation manager, validations, exports, backups, QR.
- `database/db.py` gere SQLite, schema et migrations legeres.
- `database/queries.py` contient les requetes metier.
- `database/auth.py` gere mots de passe, sessions manager, token signe de session.
- `utils/qr_token.py` gere maintenant les tokens QR HMAC V2.
- `utils/qr_generator.py` genere PNG et HTML imprimable.

## Corrections effectuees pendant cette passe

- Nouveau format QR public: `/pointage?token=<signed_token>`.
- Compatibilite maintenue avec `/pointage/<token>` et les anciens tokens.
- Token QR V2 avec `service_id`, `employee_id` optionnel, `issued_at`, `expires_at`, signature HMAC.
- `CAMPFLOW_QR_TOKEN_TTL_DAYS` ajoute comme variable de TTL QR principale.
- Liens internes pointage mis a jour pour utiliser `pointage_url()`.
- Rate-limit login deplace apres l'echec d'authentification pour ne plus bloquer un bon mot de passe.
- Docker cree `data/`, `exports/`, `backups/`, `logs/`.
- Docker CMD aligne avec Procfile: 1 worker, 2 threads, timeout 120.
- `.dockerignore` complete pour exclure fichiers runtime.

## Recommandations

1. Configurer Render Disk pour `/app/data`, et idealement `/app/exports` et `/app/backups`.
2. Definir `CAMPFLOW_SECRET_KEY` fort et stable sur Render.
3. Definir `CAMPFLOW_BASE_URL=https://campflow-v1.onrender.com`.
4. Regenerer tous les QR publics apres chaque changement de domaine, secret ou TTL.
5. Ajouter une suite minimale de tests: auth, session, pointage, validation, export, QR.
6. Ne migrer PostgreSQL qu'apres avoir isole la couche DB.

## Niveau de robustesse actuel

- Terrain pilote: acceptable avec volume persistant.
- Production commerciale: pas encore.
- SaaS multi-client: non pret.

