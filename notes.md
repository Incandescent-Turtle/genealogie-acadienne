## Record Count
`SELECT COUNT(*) AS total_humans FROM wt_individuals;`
149553
`SELECT COUNT(*) AS total_name_records FROM wt_name;`
149594

## Augmenter la Performance
L'utilisation de '+' dans Pandas pour combiner les nom de tables au lieu de .agg()

## * Securité
L'injection SQL avec les parameters ( si on prend un limite d'âge ou qqch, il faut assurer qu'il ne puisse pas être injecté )