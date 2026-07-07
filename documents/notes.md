## Documentation
On manque de bonne documentation.

## Periode Estimée
On construit une periode estimée de la vie d'une personne en utilisant ses dates de naissance et de décès et de mariage et les chose comme ça. 
On le fait bizzarement maintenant. On crée une date de naissance estimée, mais pas un date de décès estimée. Mais quand on a une vrai date de naissance, on crée une date de décès estimée. Donc on devrait aussi le faire quand on estime la date de naissance (on ajour 40 ans ou qqch comme ça).

## Separation des script d'apparier et de comparer
On devrait separer la logique -- comparer_personnes.py devrait formuler le rapport complet entre deux individus. 
apparier_personnes.py devrait utiliser correspondances_noms.py pour obtenir tous les noms à examiner, puis utiliser comparer_personnes.py pour obtenir un rapport entre les deux. PUIS, mettre tout ça dans la base de données.

## Record Count
`SELECT COUNT(*) AS total_humans FROM wt_individuals;`
149553
`SELECT COUNT(*) AS total_name_records FROM wt_name;`
149594

## Faits
Il existe 12.000 noms dans la base qui sont partagés. Ça veut dire qu'il y a 12.000 noms qui ont plus d'une personne avec ce nom.
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