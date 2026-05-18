# Démo parents / recette terrain CAMPFLOW V1

## 1. Objectif de CAMPFLOW

CAMPFLOW sert à suivre simplement les heures des saisonniers.
Le saisonnier pointe depuis un QR code affiché sur site.
Le responsable contrôle les heures avant validation.
Les oublis de scan peuvent être déclarés, puis validés ou corrigés.
L’objectif est de garder une trace claire, exportable et compréhensible.

## 2. Parcours saisonnier

1. Scanner le QR code du service concerné.
2. Choisir son nom dans la liste.
3. Cliquer sur `Commencer mon service`.
4. À la fin, rescanner le QR code et cliquer sur `Terminer mon service`.
5. En cas d’oubli, ouvrir `J'ai oublié de scanner`, remplir la demande et expliquer la raison.

Points à observer :

- Le pointage doit être rapide.
- Le saisonnier ne doit pas avoir besoin de compte.
- La demande manuelle doit rester plus longue que le scan QR.
- Le message de confirmation doit être clair.

## 3. Parcours responsable

1. Aller sur `/manager`.
2. Se connecter avec un compte responsable.
3. Au premier login, changer le mot de passe temporaire.
4. Ouvrir `Suivi semaine` pour voir les heures et les écarts par rapport à l’objectif.
5. Ouvrir `Actions à valider` pour valider, corriger ou refuser les pointages.
6. Ouvrir `Paramètres employés` pour modifier un objectif hebdomadaire.
7. Ouvrir `Exports` pour générer l’Excel.
8. Créer une sauvegarde.

Points à observer :

- Le responsable comprend-il où cliquer ?
- Les termes `valider`, `corriger`, `refuser` sont-ils clairs ?
- L’export Excel est-il lisible sans explication ?
- La sauvegarde paraît-elle rassurante et compréhensible ?

## 4. Scénario de test complet

### Étape A - Alex pointe au restaurant

1. Ouvrir le QR restaurant.
2. Sélectionner `Alex Dubois`.
3. Cliquer sur `Commencer mon service`.
4. Revenir sur le QR restaurant.
5. Sélectionner `Alex Dubois`.
6. Cliquer sur `Terminer mon service`.

Résultat attendu :

- Le pointage apparaît côté responsable dans les actions à valider.

### Étape B - Samira fait une demande manuelle ménage

1. Ouvrir le QR ménage.
2. Ouvrir `J'ai oublié de scanner`.
3. Sélectionner `Samira Petit`.
4. Remplir une plage horaire.
5. Ajouter une raison.
6. Envoyer la demande.

Résultat attendu :

- La demande apparaît côté responsable dans les demandes manuelles.

### Étape C - Responsable valide Alex

1. Aller sur `/manager`.
2. Se connecter.
3. Aller dans `Actions à valider`.
4. Trouver le créneau d’Alex.
5. Cliquer sur `Valider`.

Résultat attendu :

- Le créneau d’Alex passe en historique traité.
- Le journal d’activité indique le responsable qui a validé.

### Étape D - Responsable corrige Samira

1. Dans `Actions à valider`, trouver la demande de Samira.
2. Saisir une durée corrigée.
3. Ajouter un commentaire.
4. Cliquer sur `Corriger`.

Résultat attendu :

- La demande est corrigée.
- Le journal d’activité indique le responsable, la correction et le commentaire.

### Étape E - Export Excel

1. Aller dans `Exports`.
2. Cliquer sur `Exporter la semaine en Excel`.
3. Ouvrir le fichier généré.

Résultat attendu :

- Les heures validées/corrigées sont visibles.
- Le journal d’activité est présent dans l’Excel.

### Étape F - Sauvegarde

1. Aller dans `Exports`.
2. Cliquer sur `Créer une sauvegarde`.

Résultat attendu :

- Une sauvegarde est créée.
- L’action apparaît dans le journal d’activité.

## 5. Questions à poser aux parents

- Est-ce clair ?
- Où avez-vous hésité ?
- Quelles informations manquent ?
- Est-ce que vous l’utiliseriez en saison ?
- Le parcours saisonnier est-il assez simple ?
- Le tableau responsable est-il compréhensible ?
- L’export Excel vous paraît-il utilisable ?
- Les mots employés correspondent-ils à votre façon de travailler ?

## 6. Critères de validation avant test réel

- Aucun bug rouge pendant la démonstration.
- Le pointage saisonnier est rapide.
- Le responsable comprend les actions principales.
- Les corrections sont traçables.
- L’export Excel est lisible.
- La sauvegarde fonctionne.
- Les données affichées correspondent au scénario testé.

## 7. Points à ne PAS ajouter maintenant

- Application mobile native.
- Notifications email ou SMS.
- Intégration paie.
- Gestion avancée des contrats.
- Planning complet.
- Signature électronique.
- Messagerie interne.
- Statistiques complexes.
- Multiplication des rôles.
- Interface saisonnier avec compte et mot de passe.
- Personnalisation graphique avancée.
- Migration Supabase pendant la démo parents.

