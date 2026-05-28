# CAMPFLOW V1.5 - QR Security

## Fonctionnement

Les QR publics generent maintenant des URLs de type:

```text
/pointage?token=<signed_token>
```

Le token est signe avec HMAC-SHA256 a partir de `CAMPFLOW_SECRET_KEY`.

Le payload V2 contient:

- `service_id`
- `employee_id` optionnel, `0` pour les QR publics de service
- `issued_at`
- `expires_at`
- signature tronquee a 16 octets

Les QR publics restent sans login saisonnier. Le saisonnier scanne le service, puis choisit son profil dans la page.

## Compatibilite

Les anciens liens restent acceptes:

- `/pointage/<token>`
- anciens tokens HMAC V1 contenant seulement `service_id` et expiration
- anciens slugs de service comme fallback local

## Rotation

La rotation se fait depuis `/manager/qrcodes` via:

```text
Régénérer tous les QR codes publics
```

Chaque regeneration cree de nouveaux tokens signes et met a jour `services.qr_token`.

## Expiration

Variable:

```bash
CAMPFLOW_QR_TOKEN_TTL_DAYS=90
```

Si non definie, la valeur par defaut est 90 jours. `QR_TOKEN_TTL_DAYS` reste accepte comme ancien nom.

## Securite obtenue

- Modifier `service_id` invalide la signature.
- Modifier `employee_id`, `issued_at` ou `expires_at` invalide la signature.
- Generer un faux QR necessite `CAMPFLOW_SECRET_KEY`.
- Un token expire est refuse.
- Les anciens QR peuvent etre invalides par rotation ou par expiration.

## Limites V1.5

- Un QR public valide peut encore etre partage pendant sa duree de vie.
- Il n'y a pas de geofencing.
- Il n'y a pas de detection forte d'identite saisonnier.
- `employee_id` est supporte dans le token mais les QR publics utilisent `employee_id=0`, car l'employe est choisi apres le scan.

## Strategie future

- QR par employe si besoin de tracer un badge individuel.
- TTL plus court avec affichage manager clair de la date d'expiration.
- Revocation explicite par table `qr_tokens`.
- Detection d'anomalies par IP, heure, frequence et appareil.

