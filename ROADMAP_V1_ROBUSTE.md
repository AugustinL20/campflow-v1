# CAMPFLOW V1 - Plan d'action robustesse court terme

## Objectif

Rendre CAMPFLOW V1 fiable pour un usage reel au camping, sans migrer toute l'architecture.

Le principe est simple : garder Dash + SQLite, mais reduire les risques de perte de donnees, de conflits entre responsables, d'erreurs visibles et de blocage pendant une demo ou un test terrain.

Ce document ne demande aucune migration PostgreSQL, aucun backend separe et aucune refonte frontend.

## Tableau des priorites

| Priorite | Action | Impact | Difficulte |
|---|---|---|---|
| Critique | Mettre en place une sauvegarde automatique locale de `data/campflow.sqlite3` | Evite la perte totale des donnees en cas d'erreur ou de corruption | Faible |
| Critique | Documenter une procedure de restauration simple | Permet de revenir rapidement a une base saine avant ou pendant la saison | Faible |
| Critique | Activer SQLite WAL | Ameliore la concurrence lecture/ecriture et reduit les blocages | Faible |
| Critique | Ajouter des index sur les requetes frequentes | Accelere les vues responsable, exports et recherches semaine | Faible |
| Critique | Verifier que les erreurs affichees aux utilisateurs restent non techniques | Evite de montrer des traces Python ou messages incomprehensibles | Faible |
| Haute | Ajouter une verification d'etat avant validation/correction/refus | Evite qu'un responsable modifie un creneau deja traite par un autre | Moyenne |
| Haute | Renforcer les transactions sur les actions critiques | Reduit le risque de donnees partiellement ecrites | Moyenne |
| Haute | Ajouter un journal d'audit plus explicite | Permet de comprendre qui a valide, corrige, refuse, ajoute ou retire | Moyenne |
| Haute | Tester les QR regeneres et l'invalidation des anciens QR | Limite les fraudes et les erreurs de scan | Faible |
| Haute | Tester les exports Excel/CSV sur une base chargee | Evite une mauvaise surprise pendant la presentation ou la saison | Faible |
| Moyenne | Ajouter des tests de non-regression sur les parcours critiques | Stabilise les futures modifications | Moyenne |
| Moyenne | Clarifier les textes d'aide dans les formulaires responsables | Reduit les erreurs de saisie | Faible |
| Moyenne | Limiter les doubles clics sur les actions sensibles | Reduit les validations ou creations en double | Moyenne |
| Moyenne | Controler la taille des fichiers exports et QR | Evite d'accumuler trop de fichiers locaux | Faible |
| Basse | Nettoyer les anciens exports automatiquement | Garde le dossier `exports/` lisible | Faible |

## 1. Priorites critiques avant test terrain

Avant de tester avec de vrais saisonniers :

- confirmer que la base SQLite est sauvegardee automatiquement ;
- confirmer que la restauration est documentee et testee ;
- verifier que chaque page responsable charge sans erreur ;
- verifier que chaque page pointage charge avec un QR actif ;
- tester un ancien QR invalide ;
- tester une validation, une correction et un refus ;
- tester un ajout de personne ;
- tester un retrait de personne ;
- tester un ajout de creneau manuel ;
- tester Excel et CSV ;
- verifier qu'aucun message technique n'est visible.

## 2. Actions SQLite a faire maintenant

### Activer WAL

Objectif :

- ameliorer la concurrence entre lectures et ecritures ;
- limiter les blocages quand plusieurs personnes pointent ou quand un responsable consulte les donnees.

Checklist :

- [ ] activer `PRAGMA journal_mode=WAL` a l'initialisation ;
- [ ] verifier que le fichier `.wal` est bien cree ;
- [ ] tester pointage + consultation responsable en meme temps ;
- [ ] documenter que les fichiers SQLite associes doivent etre sauvegardes correctement.

### Ajouter des index utiles

Objectif :

- accelerer les vues semaine ;
- accelerer les exports ;
- accelerer les recherches par statut.

Index a prevoir :

- [ ] `work_sessions(start_time)` ;
- [ ] `work_sessions(validation_status)` ;
- [ ] `work_sessions(employee_id)` ;
- [ ] `work_sessions(service_id)` ;
- [ ] `manual_time_requests(status)` ;
- [ ] `manual_time_requests(created_at)` ;
- [ ] `validation_logs(timestamp)` ;
- [ ] `services(qr_token)`.

### Verifier les contraintes simples

Objectif :

- eviter des donnees incoherentes.

Checklist :

- [ ] empecher une duree negative ;
- [ ] refuser une heure de fin avant l'heure de debut ;
- [ ] verifier que le service existe ;
- [ ] verifier que la personne est active lors d'une creation de creneau ;
- [ ] conserver l'historique d'une personne retiree.

## 3. Protections multi-utilisateur simples

Objectif : eviter les conflits quand deux responsables agissent en meme temps.

Actions :

- [ ] verifier l'etat courant avant de valider, corriger ou refuser ;
- [ ] refuser une action si le creneau n'est plus en attente ;
- [ ] afficher un message clair : `Ce creneau a deja ete traite. Rechargez la page.` ;
- [ ] enregistrer l'action responsable dans le journal ;
- [ ] ajouter un horodatage de derniere modification exploitable ;
- [ ] eviter les doubles clics sur les boutons critiques ;
- [ ] tester deux validations successives du meme creneau.

## 4. Sauvegarde automatique locale

Objectif : eviter la perte de donnees pendant la saison.

Sauvegarde recommandee :

- sauvegarde quotidienne de `data/campflow.sqlite3` ;
- conservation de plusieurs versions ;
- copie dans un dossier distinct, par exemple `backups/` ;
- export manuel possible avant chaque grosse modification ;
- documentation de restauration.

Checklist :

- [ ] creer un dossier `backups/` ;
- [ ] definir une convention de nommage : `campflow_YYYY-MM-DD_HH-MM.sqlite3` ;
- [ ] automatiser une sauvegarde quotidienne ;
- [ ] tester une restauration sur une copie ;
- [ ] documenter la procedure dans `DEPLOYMENT.md` ou un fichier dedie ;
- [ ] verifier que `data/` et `backups/` sont persistants en production locale.

## 5. Gestion des erreurs utilisateur

Objectif : aucun message technique visible pour les saisonniers ou responsables.

Checklist :

- [ ] tester un QR ancien ;
- [ ] tester un QR invalide ;
- [ ] tester un pointage sans personne selectionnee ;
- [ ] tester une demande manuelle incomplete ;
- [ ] tester une date invalide ;
- [ ] tester une heure invalide ;
- [ ] tester une fin avant debut ;
- [ ] tester un export sans donnees ;
- [ ] tester un export pendant que des donnees sont modifiees ;
- [ ] verifier que les messages restent en francais clair.

Messages attendus :

- `Ce code QR n'est plus valide. Demandez au responsable le dernier code QR imprime.`
- `Selectionnez un profil ou renseignez prenom et nom.`
- `Tous les champs sont obligatoires.`
- `La fin doit etre apres le debut.`
- `Ce creneau a deja ete traite. Rechargez la page.`

## 6. Tests a faire avant demo parents

Parcours minimum :

- [ ] lancer l'application ;
- [ ] ouvrir `/manager` ;
- [ ] verifier les boutons vers toutes les sous-pages ;
- [ ] ouvrir `/manager/suivi` ;
- [ ] verifier objectif semaine, heures validees, ecart, statut ;
- [ ] ouvrir `/manager/actions` ;
- [ ] valider un pointage ;
- [ ] corriger un pointage ;
- [ ] refuser un pointage ;
- [ ] ouvrir `/manager/ajouter` ;
- [ ] ajouter une personne ;
- [ ] ajouter un creneau manuel ;
- [ ] ouvrir `/manager/parametres` ;
- [ ] modifier un objectif hebdomadaire ;
- [ ] retirer une personne ;
- [ ] ouvrir `/manager/exports` ;
- [ ] generer Excel ;
- [ ] generer CSV ;
- [ ] ouvrir `/manager/qrcodes` ;
- [ ] generer un QR de service ;
- [ ] verifier que l'ancien QR est invalide ;
- [ ] ouvrir `/pointage/<nouveau_jeton>` ;
- [ ] faire un pointage saisonnier ;
- [ ] verifier que le pointage arrive dans les actions responsable ;
- [ ] verifier qu'aucune erreur rouge Dash n'apparait.

## 7. Ce qu'on repousse a V1.5/V2

Ne pas faire maintenant :

- migration PostgreSQL ;
- backend API separe ;
- frontend React/Next.js ;
- authentification complete multi-utilisateur ;
- stockage objet cloud ;
- file d'attente pour exports ;
- workers separes ;
- multi-camping ;
- facturation SaaS ;
- Kubernetes ;
- autoscaling ;
- monitoring complet type Prometheus/Grafana ;
- SSO ;
- permissions avancees par service.

Ces sujets sont importants, mais ils appartiennent a la V1.5 ou a la V2. Les faire maintenant ralentirait la stabilisation de la V1.

## Checklist executable courte

- [ ] Activer WAL SQLite.
- [ ] Ajouter les index SQLite prioritaires.
- [ ] Mettre en place une sauvegarde locale automatique.
- [ ] Tester une restauration.
- [ ] Verifier les messages d'erreur utilisateur.
- [ ] Proteger les transitions de statut contre les doubles validations.
- [ ] Verifier les exports Excel/CSV.
- [ ] Verifier les QR regeneres.
- [ ] Tester un pointage avec nouveau jeton QR.
- [ ] Tester toutes les pages responsable.
- [ ] Documenter la procedure de demo.
- [ ] Documenter la procedure de sauvegarde/restauration.

## Decision

CAMPFLOW V1 doit rester simple pour la saison locale.

La bonne priorite court terme est :

1. proteger les donnees ;
2. eviter les erreurs visibles ;
3. limiter les conflits entre responsables ;
4. rendre les sauvegardes et restaurations simples ;
5. garder la migration cloud pour V1.5.
