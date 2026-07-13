# Généalogie acadienne

Outils Python pour explorer une base de données généalogique **WebTrees** :
repérer les personnes en double entre les arbres, calculer des statistiques et
détecter des erreurs de saisie.

Les scripts **lisent** la base WebTrees (tables `wt_`*). Seul
`apparier_personnes.py` **écrit**, et uniquement dans sa propre table de
résultats (`person_comparisons`).

Les scripts ne contiennent aucune donnée : ils se connectent à la base
MySQL/MariaDB d'une instance **WebTrees** existante. 

## Une instance WebTrees locale

Si on veut avoir une instance WebTrees (ce n'est pas necessaire pour les scripts)

Le plus simple :

1. Installer **[Herd](https://herd.laravel.com/)** — il fournit PHP et une base
  MySQL/MariaDB locale.
2. Installer **[WebTrees](https://webtrees.net/)** et le servir via Herd (par ex.
  sur `http://webtrees.test`).
3. Entrer les credentials de la base de données pour connecter.

Par défaut, les tables portent le préfixe `wt_` (modifiable via `DB_PREFIX`,
voir `scripts/db.py`).

## Installation

```bash
git clone <url-du-dépôt>
cd généalogie-acadienne

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Python 3.13 est recommandé.

## Configuration

Copier `.env.example` vers `.env` et remplir les identifiants de la base
WebTrees :

```
DB_HOST="127.0.0.1"
DB_USER="root"
DB_PASS="..."
DB_NAME="webtrees"
DB_PORT="3306"
```

Le fichier `.env` n'est pas versionné.

## Fichiers principaux


| Fichier                      | Rôle                                                                                                |
| ---------------------------- | --------------------------------------------------------------------------------------------------- |
| `scripts/db.py`              | Connexion partagée à la base (lit `.env`) et petits utilitaires SQL.                                |
| `scripts/trouver_doublons/`  | La tâche principale : trouver les personnes en double.                                              |
| `correspondances_noms.py`    | Charge tous les noms et repère ceux partagés entre arbres.                                          |
| `personnes.py`               | Modèle `Personne` + chargement depuis la base (une personne, ou des milliers en lots).              |
| `comparer_personnes.py`      | Compare **deux** personnes et renvoie un rapport (métriques + verdicts).                            |
| `apparier_personnes.py`      | **Point d'entrée** : assemble les trois modules et enregistre les paires dans `person_comparisons`. |
| `scripts/statistiques.py`    | Statistiques générales (durée de vie, âges, etc.). Lecture seule.                                   |
| `scripts/trouver_erreurs.py` | Repère les erreurs de saisie (dates impossibles, etc.). Lecture seule.                              |
| `documents/`                 | Notes et questions de travail.                                                                      |
| `rapports/`                  | Sorties générées par les scripts.                                                                   |




## Exécution

Avec le `.venv` activé et le `.env` configuré :

```bash
# Trouver les doublons -> écrit dans la table `person_comparisons`
python scripts/trouver_doublons/apparier_personnes.py

# Statistiques (lecture seule)
python scripts/statistiques.py

# Détection d'erreurs de saisie (lecture seule)
python scripts/trouver_erreurs.py
```

`apparier_personnes.py` crée la table `person_comparisons` si besoin, télécharge
en lot toutes les personnes qui partagent un nom, les compare deux à deux, et
enregistre chaque paire ayant au moins un critère concordant.

## Les Prochaines Étapes
### Où on est en ce moment
Maintenant, ces scripts marchent pour trouver les paires d'individus qui sont peut-être les même, basé sur les critère de naissance, décès, sepulture, batpême, enfants, parents, et mariages. Les scripts sont très vite, et peut examiner une base de 150.000 individus, trouver 600.000 paires qui partagent un nom, les analyser, et présenter celles qui partagent les critères -- en moins d'une minute.

On cherche les individus qui ont exactement les mêmes noms. On ne cherche pas les variantes orthographiques ni les homonymes. 

### L'Amélioration de trouver les paires
La première chose qu'on pourrait faire, c'est inclure les variantes orthographiques dans nos comparaisons. Les homonymes, les erreurs de saiser, l'abscense ou l'ajout d'un deuxième nom, etc.

Une Mary pourrait être une Marie dans la base, par exemple, ou une Marie Louise Comeaux pourrait aussi être Louise Comeaux.

Cette méthode donnerait plus de paires --- avec les scripts actuels, on en a environ 600.000, et avec ces modifications-ci, on en aurait peut-être quelques millions. Mais nos scripts sont vites, donc les temps d'exécution ne posent pas de problème.

### L'Attribution d'un score
On garde entre 18.000 et 29.000 paires d'indivus qui partagent un critère ou plus -- c'est impossible de faire toutes ces comparaisons à la main.

Donc, pour économiser du temps, on veut d'abord examiner les paires dont on est déjà assez certaines qu'ils sont les mêmes -- celles qui sont plus facile à comparer. 

On voudrait inclure les faits contradictoire, les periodes estimées impossibles ou improbables, le nombre de critère partagés, quels critères sont partagées, et les choses comme ça. On commencerait par celles qui partage 7 critères j'imagine.

Donc, on devrait créer une algorithme, ou une formule, pour attribuer un score aux paires pour nous dire lequelles sont les plus probables d'être les mêmes. 

### Que faire des résultats ?
En ce moment, on a tous les paires ; mais qu'est-ce qu'on devrait faire en ce moment-ci ? 

Les paires doivent être présentées à un expert afin de vérifier s'il s'agit bien des mêmes personnes ou non. Pour faire ceci, on ne peut pas vraiment utiliser WebTrees, parce que il est trop lent et il n'est pas conçu pour faire des comparaisons. On ne peut pas utiliser un fichier Excel non-plus, pour les mêmes raisons. 

D'après moi, on devrait créer un "site web" simple pour afficher des paires. On pourrait afficher une paire côte à côte : ça renderait souligner des similitudes et l'information contradictoire plus facile. On connecterait à la base de données et chargerait toutes les paires sur le site, et montrerait des boutons pour marquer une correspondance à chacun. Cette méthode est dynamique et conçu prècisement pour faire des comparaisons.

Aussi, plusiers personnes pourraient travailler sur la tâche de vérification en même temps.