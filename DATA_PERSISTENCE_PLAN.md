# CAMPFLOW V1 - Data Persistence Plan

## Probleme

Render peut avoir un filesystem ephemere. Sans disque persistant, les fichiers suivants peuvent disparaitre au redeploiement ou au redemarrage:

- `data/campflow.sqlite3`
- `exports/*.xlsx`
- `exports/*.csv`
- `exports/campflow_qr_codes_printable.html`
- `exports/qr_codes/*`
- `backups/*.sqlite3`
- `logs/*`

## Strategie V1 recommandee

### Minimum obligatoire

Configurer un Render Disk monte sur:

```text
/app/data
```

C'est le minimum pour ne pas perdre les pointages.

### Recommande

Configurer aussi:

```text
/app/exports
/app/backups
```

Si Render ne permet qu'un point de montage simple, monter un disque sur `/app/data` et planifier un export manuel regulier reste preferable a aucune persistance.

## Sauvegardes

La sauvegarde locale copie SQLite vers `backups/`. C'est utile seulement si `backups/` est persistant ou telecharge regulierement.

Procedure V1:

1. Chaque fin de semaine, exporter Excel.
2. Creer une sauvegarde depuis `/manager/exports`.
3. Telecharger le fichier de sauvegarde si possible.
4. Conserver une copie hors Render.

## Limites

- Les backups locaux ne protegent pas contre la perte du disque Render.
- SQLite n'est pas ideal pour ecritures concurrentes.
- Les exports locaux ne sont pas une archive fiable si non telecharges.

## Strategie V1.5

- Render Disk pour SQLite.
- Export Excel hebdomadaire telecharge.
- Backup SQLite telecharge avant chaque redeploiement important.
- Migration PostgreSQL planifiee si usage commercial ou plusieurs etablissements actifs.

