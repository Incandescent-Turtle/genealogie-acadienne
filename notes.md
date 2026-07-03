## Record Count
`SELECT COUNT(*) AS total_humans FROM wt_individuals;`
149553
`SELECT COUNT(*) AS total_name_records FROM wt_name;`
149594

## Faits
Il existe 15.000 noms dans la base qui sont partagés. Ça veut dire qu'il y a 15.000 noms qui ont plus d'une personne avec ce nom.
Il en existe 316 avec le nom Marie LeBlanc, répartis sur 42 arbres.


## Augmenter la Performance
L'utilisation de '+' dans Pandas pour combiner les nom de tables au lieu de .agg()

## * Securité
L'injection SQL avec les parameters ( si on prend un limite d'âge ou qqch, il faut assurer qu'il ne puisse pas être injecté )

## Personnes qui sont les mêmes je pense :
Zacharie Agapit d'ENTREMONT : D'ENTREMONT et DUON
http://webtrees.test/index.php?route=%2Ftree%2FDUON%2Findividual%2FI0669%2FZacharie-Agapit-d-039-Entremont#tab-tree
http://webtrees.test/index.php?route=%2Ftree%2FDENTREMONT%2Findividual%2F1590%2FZacharie-Agapit-d-039-ENTREMONT#tab-tree

Abbie Thibault : AMIRAULT et THIBAULT
http://webtrees.test/index.php?route=%2Ftree%2FTHIBAULT%2Findividual%2FI0271%2FAbbie-Agnes-Thibault#tab-tree
http://webtrees.test/index.php?route=%2Ftree%2FAMIRAULT%2Findividual%2FI3476%2FAbbie-Thibault#tab-tree

abraham mius d entremont de pleinmarais

## Âge de ___
Âge au premier mariage
sex	moyenne	médiane
F 24.2 22.0
M 27.5 26.0

Âge à la naissance du premier enfant
sexe	nombre	moyenne	médiane
F 25.1 24.0
M 28.5 28.0

Event	Records	Mean age	Median age
Baptism (BAPM) 34,132 0.2 yr (~2–3 months) 0.0 yr
Christening (CHR) 4 23.5 yr 7.9 yr
Both combined 34,136 0.2 yr 0.0 yr
ça veut dire que les CHR ne sont pas vraiment utilisés dans cette base. Et que les BAPM se passent à la naissance.