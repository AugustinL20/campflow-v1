# CAMPFLOW V2 - Etude architecture robuste et scalable

## Objectif

Preparer CAMPFLOW a une architecture capable de supporter beaucoup d'utilisateurs simultanes, avec une hypothese volontairement ambitieuse de 10 000 utilisateurs en meme temps.

Les priorites sont :

- robustesse ;
- usage multi-utilisateur ;
- prevention de la perte de donnees ;
- evolution commerciale possible ;
- migration progressive sans casser la V1.

Ce document ne propose pas de reecrire CAMPFLOW d'un coup. Il sert a choisir une trajectoire technique.

## 1. Audit de l'architecture actuelle

### Application

CAMPFLOW V1 est une application Dash monolithique.

Elle contient :

- une interface saisonnier pour le pointage par code QR ;
- une interface responsable pour valider, corriger, refuser, ajouter des personnes, ajouter des heures, exporter et gerer les codes QR ;
- une base SQLite locale dans `data/campflow.sqlite3` ;
- des exports locaux dans `exports/` ;
- des callbacks Dash qui lisent et ecrivent directement dans la base ;
- une protection responsable par mot de passe simple ;
- une generation locale des fichiers Excel, CSV et codes QR.

### Points forts actuels

- Simple a lancer et comprendre.
- Peu de dependances.
- Fonctionne bien pour un camping local, une equipe limitee et un seul serveur.
- Les donnees sont dans un fichier unique facile a sauvegarder.
- Le produit avance vite car l'interface, la logique et la base sont dans le meme projet.

### Points faibles actuels

- L'application n'est pas separee entre frontend, backend et base de donnees.
- Les callbacks Dash font a la fois interface, logique metier et acces donnees.
- SQLite est pratique mais limite en ecriture concurrente.
- Les exports sont synchrones et peuvent bloquer l'experience utilisateur.
- Les fichiers sont stockes localement sur le serveur.
- L'authentification responsable est minimale.
- Il n'y a pas de roles utilisateurs solides ni de journal d'audit complet.
- La concurrence entre plusieurs responsables peut provoquer des validations simultanees contradictoires.

## 2. Limites identifiees

### SQLite

SQLite est adapte a une V1 locale, mais pas a 10 000 utilisateurs simultanes.

Limites principales :

- un seul fichier de base ;
- verrouillages en ecriture ;
- risque de contention lors de nombreux pointages simultanes ;
- sauvegardes et restauration moins propres en environnement cloud multi-instance ;
- pas de pool de connexions centralise ;
- pas d'outils natifs aussi forts que PostgreSQL pour l'observabilite, les index avances, les verrous applicatifs ou les migrations complexes.

Conclusion : SQLite peut rester pour une V1 locale robuste, mais doit etre remplace par PostgreSQL pour le cloud.

### Callbacks Dash

Dash est efficace pour construire vite une application interne, mais les callbacks actuels portent trop de responsabilites.

Limites :

- les callbacks lisent et ecrivent directement dans la base ;
- la logique metier est melangee a l'interface ;
- les gros tableaux peuvent devenir lourds ;
- une action lente peut ralentir la session utilisateur ;
- le modele devient difficile a tester si l'application grandit ;
- Dash n'est pas ideal comme frontend principal d'un SaaS grand public avec beaucoup de sessions.

Conclusion : Dash peut rester pour une console responsable V1/V1.5, mais la logique metier doit migrer vers une API backend.

### Exports synchrones

Actuellement, Excel et CSV sont generes directement pendant l'action utilisateur.

Limites :

- un gros export peut bloquer le worker web ;
- plusieurs exports simultanes peuvent saturer CPU/RAM ;
- un export peut echouer si le processus web redemarre ;
- les fichiers locaux peuvent disparaitre selon l'hebergement ;
- pas de suivi d'etat : en cours, termine, echoue.

Conclusion : en V1.5/V2, les exports doivent etre des taches asynchrones avec stockage objet.

### Stockage local

Les fichiers sont dans `exports/` et la base dans `data/`.

Limites :

- si le serveur est recree, les fichiers peuvent etre perdus ;
- difficile de scaler sur plusieurs instances ;
- un fichier genere sur une instance n'est pas visible depuis une autre ;
- les sauvegardes dependent de la discipline d'exploitation.

Conclusion : les exports, QR et pieces generees doivent aller vers un stockage objet en cloud.

### Absence de vraie authentification

La V1 utilise un mot de passe responsable global.

Limites :

- pas de comptes individuels ;
- pas de roles fins ;
- pas de tracabilite fiable par utilisateur ;
- pas de rotation simple des acces ;
- pas de recuperation de mot de passe ;
- partage possible du mot de passe.

Conclusion : une V2 doit avoir des comptes, roles, sessions securisees et journal d'audit.

### Concurrence responsable

Deux responsables peuvent agir en meme temps sur les memes pointages.

Risques :

- double validation ;
- correction ecrasee ;
- refus apres validation ;
- exports incoherents pendant une validation ;
- absence de detection "ce creneau a deja ete modifie".

Conclusion : il faut ajouter du verrouillage optimiste, des horodatages de version et des transactions solides.

## 3. Architecture cible

### Vue d'ensemble

Architecture cible recommandee pour CAMPFLOW V2 :

```text
Frontend web/mobile
        |
        v
Backend API
        |
        +--> PostgreSQL
        |
        +--> File d'attente de taches
        |        |
        |        v
        |     Workers exports / QR / notifications
        |
        +--> Stockage objet
        |
        +--> Logs / monitoring / alertes
```

### Frontend

Options possibles :

- conserver Dash pour l'interface responsable en V1.5 ;
- construire une interface web dediee en React, Next.js ou equivalent pour V2 ;
- garder une page pointage tres simple, rapide et mobile-first.

Recommandation :

- V1.5 : Dash reste acceptable pour l'admin/responsable.
- V2 : frontend separe, mobile-first, connecte a une API.

### Backend API

Le backend doit devenir la source unique de logique metier.

Responsabilites :

- pointage arrivee/depart ;
- validation/correction/refus ;
- demandes manuelles ;
- objectifs hebdomadaires ;
- gestion des personnes ;
- generation et rotation des QR ;
- exports ;
- audit ;
- droits d'acces.

Stack possible :

- FastAPI en Python ;
- SQLAlchemy ou SQLModel ;
- Alembic pour les migrations ;
- Pydantic pour validation des donnees ;
- Gunicorn/Uvicorn pour le deploiement.

Pourquoi FastAPI :

- reste dans l'ecosysteme Python ;
- tres adapte a une API claire ;
- facilite les tests ;
- separe proprement interface et logique.

### Base PostgreSQL

PostgreSQL devient la base centrale.

Avantages :

- meilleure concurrence ;
- transactions robustes ;
- index performants ;
- contraintes plus strictes ;
- sauvegardes managables ;
- extensions utiles ;
- compatible avec hebergements cloud.

Tables principales a conserver et renforcer :

- `employees` ;
- `services` ;
- `work_sessions` ;
- `manual_time_requests` ;
- `validation_logs`.

Tables a ajouter en V1.5/V2 :

- `users` ;
- `roles` ;
- `audit_events` ;
- `export_jobs` ;
- `qr_tokens` ou historique des rotations QR ;
- `organizations` si CAMPFLOW devient multi-camping ;
- `sites` ou `campings` ;
- `employee_contracts` pour objectifs, contrats, dates de saison.

### Stockage exports

Remplacer `exports/` local par un stockage objet :

- S3 ;
- Google Cloud Storage ;
- Azure Blob ;
- Supabase Storage ;
- Cloudflare R2.

Les exports doivent avoir :

- un identifiant ;
- un statut ;
- une date de creation ;
- un proprietaire ;
- une URL temporaire signee ;
- une duree de conservation.

### Logs et observabilite

Ajouter :

- logs applicatifs structures ;
- audit metier ;
- suivi des erreurs ;
- suivi des temps de reponse ;
- alertes sur erreurs export, echec DB, taux d'erreur eleve.

Outils possibles :

- Sentry pour erreurs ;
- Grafana/Prometheus pour metriques ;
- logs JSON vers un agregateur ;
- logs cloud natifs selon l'hebergeur.

### Authentification

Pour V1.5 :

- comptes responsables ;
- mot de passe hash ;
- sessions serveur ou JWT court ;
- roles simples : responsable, saisonnier, admin.

Pour V2 :

- multi-organisation ;
- invitation utilisateur ;
- reset mot de passe ;
- eventuellement SSO ;
- journal des connexions ;
- droits par camping/service.

### Rate limiting

Important pour les pages de pointage par QR.

Limiter :

- tentatives de pointage par IP ;
- tentatives par employe/service ;
- generations QR ;
- connexions responsables ;
- exports.

Objectif :

- eviter abus ;
- limiter les erreurs accidentelles ;
- proteger le backend.

### Sauvegardes

V1 locale :

- sauvegarde quotidienne du fichier SQLite ;
- copie externe du dossier `data/` ;
- sauvegarde des exports importants.

V1.5 cloud :

- sauvegardes PostgreSQL automatiques ;
- retention 7 a 30 jours ;
- test de restauration ;
- stockage objet versionne.

V2 SaaS :

- sauvegarde continue ou PITR ;
- plan de reprise ;
- chiffrement ;
- separation des environnements ;
- monitoring des backups.

## 4. Roadmap de migration

### Etape 1 - V1 robuste camping local

Objectif : rendre la V1 fiable pour une vraie saison, sans tout reecrire.

A faire :

- garder Dash + SQLite ;
- ajouter sauvegarde automatique de `data/campflow.sqlite3` ;
- ajouter mode WAL SQLite ;
- ajouter index utiles ;
- ajouter contraintes de validation supplementaires ;
- eviter les messages techniques visibles ;
- renforcer les transactions critiques ;
- mieux journaliser les actions responsable ;
- ajouter detection de modification concurrente simple ;
- garder les exports locaux mais mieux gerer les erreurs ;
- documenter la procedure de restauration.

Ce qu'il ne faut pas faire encore :

- ne pas migrer tout le frontend ;
- ne pas creer une architecture microservices ;
- ne pas ajouter trop d'abstractions.

### Etape 2 - V1.5 cloud PostgreSQL

Objectif : separer les donnees du serveur et permettre un hebergement cloud plus fiable.

A faire :

- migrer SQLite vers PostgreSQL ;
- introduire SQLAlchemy ou une couche repository ;
- ajouter Alembic pour les migrations ;
- utiliser des variables d'environnement pour `DATABASE_URL` ;
- stocker les exports dans un stockage objet ;
- ajouter une table `export_jobs` ;
- garder Dash comme interface responsable ;
- ajouter vrais comptes responsables ;
- ajouter logs applicatifs et erreurs Sentry ;
- ajouter rate limiting sur pointage et connexion ;
- deploiement avec une ou plusieurs instances web.

Resultat attendu :

- moins de risque de perte de donnees ;
- meilleure concurrence ;
- hebergement cloud plus propre ;
- base prete pour V2.

### Etape 3 - V2 SaaS scalable

Objectif : faire de CAMPFLOW un produit multi-clients scalable.

A faire :

- frontend separe ;
- backend API FastAPI ;
- PostgreSQL managé ;
- file d'attente pour exports et traitements longs ;
- workers separes ;
- stockage objet ;
- authentification complete ;
- multi-organisation ;
- roles et permissions ;
- audit complet ;
- observabilite ;
- tests automatises plus larges ;
- CI/CD ;
- sauvegardes et restauration testees.

Objectif 10 000 utilisateurs simultanes :

- plusieurs instances frontend ;
- plusieurs instances backend ;
- pool de connexions PostgreSQL ;
- cache si necessaire ;
- file d'attente pour taches lourdes ;
- CDN pour fichiers statiques ;
- stockage objet pour exports ;
- monitoring et autoscaling.

## 5. Ce qu'il faut modifier maintenant sans tout casser

Priorite immediate pour stabiliser la V1 :

1. Activer SQLite WAL.
2. Ajouter des index sur les colonnes de recherche frequentes.
3. Ajouter une sauvegarde automatique du fichier SQLite.
4. Ajouter une couche de fonctions metier plus claire entre callbacks et base.
5. Ajouter des tests de non-regression sur les parcours critiques.
6. Ajouter un journal d'audit plus explicite pour les actions responsables.
7. Verrouiller les transitions de statut avec verification de l'etat precedent.
8. Eviter tout message technique visible.
9. Documenter la procedure de demo, sauvegarde et restauration.

Ne pas faire maintenant :

- reecrire l'interface ;
- migrer directement vers un SaaS complet ;
- introduire Kubernetes ;
- ajouter une file d'attente avant d'avoir PostgreSQL ;
- multiplier les services.

## 6. Synthese

CAMPFLOW V1 est coherent pour un camping local, une petite equipe et une presentation.

Pour 10 000 utilisateurs simultanes, l'architecture actuelle Dash + SQLite + fichiers locaux n'est pas suffisante. La cible doit separer :

- frontend ;
- backend API ;
- PostgreSQL ;
- workers ;
- stockage objet ;
- authentification ;
- logs ;
- sauvegardes.

La bonne strategie est progressive :

1. rendre la V1 locale fiable ;
2. migrer la base et les fichiers vers le cloud ;
3. construire une V2 SaaS separee et scalable.

Cette trajectoire limite les risques, protege les donnees et evite de casser le produit qui fonctionne deja.
