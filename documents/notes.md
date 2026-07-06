## Record Count
`SELECT COUNT(*) AS total_humans FROM wt_individuals;`
149553
`SELECT COUNT(*) AS total_name_records FROM wt_name;`
149594

## Faits
Il existe 15.000 noms dans la base qui sont partagés. Ça veut dire qu'il y a 15.000 noms qui ont plus d'une personne avec ce nom.
par exemple, il en existe 316 avec le nom Marie LeBlanc, répartis sur 42 arbres.

## * Securité
L'injection SQL avec les parameters ( si on prend un limite d'âge ou qqch, il faut assurer qu'il ne puisse pas être injecté )

## Les deuxièmes prénoms
Souvant, les filles avec le prénom "Marie" étaient appelées par leur deuxième prénom.
Donc, dans les archives, on manque les prénoms comme "Marie" parfois.
Ce serait bien de regarder tous les prénoms. Par exemple:

Si on avait deux personnes:

`Marie Louise LeBlanc` et `Louise Geneviève LeBlanc`

On voudrait comparer "Marie LeBlanc" et "Louise LeBlanc" (de M. L. LeBlanc) contre "Louise LeBlanc" and "Geneviève LeBlanc" pour identifier les personnes qui ont peut-être le même nom. Ici on trouverait que les deux peuvent être "Louise LeBlanc". Parce qu'elles partagent un nom, c'est possible qu'elles sont la même personne.

C'est plus clair avec cet exemple-ci:

Marie Alma Comeaux 
Alma Comeaux 

Ici on veux comparer "Marie Comeaux" et "Alma Comeaux" (de M. A. Comeaux) contre "Alma Comeaux", et on trouverait qu'elles sont toutes les deux "Alma Comeaux". 

Pour faire ça, on peut simplement examiner toutes les personnes qui ont un nom en commun avec cette personne (toutes les Marie LeBlanc, toutes les Alma LeBlanc)

## Quand les actes de mariage sont manquants

## Personnes qui sont les mêmes je pense :
Zacharie Agapit d'ENTREMONT : D'ENTREMONT et DUON
http://webtrees.test/index.php?route=%2Ftree%2FDUON%2Findividual%2FI0669%2FZacharie-Agapit-d-039-Entremont#tab-tree
http://webtrees.test/index.php?route=%2Ftree%2FDENTREMONT%2Findividual%2F1590%2FZacharie-Agapit-d-039-ENTREMONT#tab-tree

Abbie Thibault : AMIRAULT et THIBAULT
http://webtrees.test/index.php?route=%2Ftree%2FTHIBAULT%2Findividual%2FI0271%2FAbbie-Agnes-Thibault#tab-tree
http://webtrees.test/index.php?route=%2Ftree%2FAMIRAULT%2Findividual%2FI3476%2FAbbie-Thibault#tab-tree

abraham mius d entremont de pleinmarais

## statistiques.md
Regarde ce fichier pour voir les statistiques de personnes, par exemple la moyenne âge de naissance.