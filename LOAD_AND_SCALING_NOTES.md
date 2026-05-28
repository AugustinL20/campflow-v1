# CAMPFLOW V1 - Load And Scaling Notes

## Hypotheses V1

- 1 camping.
- 3 a 10 services.
- 10 a 80 saisonniers.
- 20 a 300 scans QR par jour.
- 1 a 3 managers.

## Limites techniques

| Composant | Limite |
| --- | --- |
| Render Free | Cold starts, CPU limite, latence au premier scan |
| Dash | Callbacks serveur, pas ideal pour tres forte concurrence |
| SQLite | Ecritures concurrentes limitees, un seul writer effectif |
| Gunicorn 1 worker / 2 threads | Suffisant V1, limite si beaucoup de scans simultanes |
| Exports | Pandas/OpenPyXL peuvent bloquer le worker pendant generation |

## Estimation honnete

- 1 a 5 utilisateurs simultanes: OK.
- 5 a 15 utilisateurs simultanes: probablement OK si scans courts.
- 15+ utilisateurs simultanes: risque de lenteur, surtout pendant export.
- Pic de scans simultanes au changement de service: acceptable si moins de 10-15 personnes en meme temps.

## Goulots d'etranglement

1. SQLite en ecriture.
2. Exports Excel synchrones.
3. Cold start Render.
4. Dash callbacks longs.
5. Absence de file de jobs.

## Simulation legere recommandee

Avant grosse saison:

1. 20 scans arrivee en 2 minutes.
2. 20 scans depart en 2 minutes.
3. 1 export Excel pendant que 5 scans arrivent.
4. 2 managers ouverts sur `/manager/actions`.

## Decision V1

La V1 est adaptee a un pilote terrain et un camping avec volume faible a modere. Pour commercialisation multi-client, PostgreSQL et une architecture API plus classique deviendront necessaires.

