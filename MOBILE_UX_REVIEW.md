# CAMPFLOW V1 - Mobile UX Review

## Etat actuel

L'interface saisonnier est globalement mobile-first:

- largeur limitee;
- gros bouton principal;
- texte clair;
- feedback de confirmation;
- historique du jour;
- bloc "J'ai oublie de scanner" replie.

## Corrections deja presentes

- Feedback clair apres pointage.
- Bouton principal large.
- Message "Un clic suffit. Attendez la confirmation avant de fermer la page."
- `dcc.Loading` autour du feedback.
- Rate-limit pointage pour eviter les abus.
- Messages d'erreur simples.
- Taille des inputs mobile pour eviter le zoom iOS.

## Points de fragilite

| Gravite | Probleme | Recommandation |
| --- | --- | --- |
| Haute | Cold start Render peut faire croire que le scan ne marche pas. | Ajouter une page/message "Chargement CAMPFLOW..." plus visible si possible. |
| Moyenne | Double clic rapide avant retour serveur. | Idealement desactiver le bouton pendant l'appel callback. |
| Moyenne | Dropdown Dash peut etre moins fluide sur mobile ancien. | Tester iPhone Safari et Android Chrome reels. |
| Moyenne | Si le reseau coupe apres clic, l'utilisateur ne sait pas si le pointage est passe. | Garder historique du jour visible et conseiller de verifier la ligne ajoutee. |
| Basse | Le formulaire manuel est plus long mais volontairement secondaire. | OK V1. |

## Tests terrain conseilles

1. iPhone Safari, 4G moyenne.
2. Android Chrome, 4G moyenne.
3. Scan QR apres cold start Render.
4. Double tap rapide sur "Commencer mon service".
5. Scan arrivee puis depart.
6. Service ouvert sur un autre service.
7. Demande manuelle avec erreur de format.

## Quick wins futurs

- Desactiver visuellement le bouton immediatement au clic cote client.
- Afficher "Pointage en cours..." dans le bouton.
- Ajouter une ligne "Derniere action enregistree" persistante dans l'interface.
- Ajouter une page d'aide manager: "Que faire si un saisonnier ne voit pas sa confirmation ?"

