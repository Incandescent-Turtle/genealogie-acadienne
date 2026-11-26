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
voir `src/genealogie_acadienne/donnees/db.py`).

## Installation

```bash
git clone <url-du-dépôt>
cd généalogie-acadienne

uv sync                      # crée .venv (Python 3.13) et installe le paquet en mode éditable + pytest
uv run pytest
# (optionnel) l'environnement de travail complet, avec Jupyter, etc. :
# uv pip install -r requirements.txt
```

Python 3.13 ou plus récent est requis (épinglé dans `.python-version`). Sans
[uv](https://docs.astral.sh/uv/) : `pip install -e . --group dev` (pip ≥ 25.1).

### Depuis un autre projet

Le dépôt s'installe comme un paquet Python (`genealogie_acadienne`) :

```bash
# copie locale, en mode éditable
uv add --editable ../genealogie-acadienne

# depuis git, épinglé sur un commit précis (recommandé pour la reproductibilité)
uv add "genealogie-acadienne @ git+https://github.com/<compte>/genealogie-acadienne.git@<hash_du_commit>"
```

```python
from genealogie_acadienne import DBConfig, get_connection, charger_groupe, comparer

conn = get_connection(DBConfig(host="127.0.0.1", user="root", password="...", database="webtrees"))
```

Importer le paquet n'ouvre **aucune** connexion et ne lit **pas** le `.env`.
Sans `DBConfig`, `get_connection()` lit les variables d'environnement
`DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`, `DB_PORT` (et `DB_PREFIX` pour le
préfixe des tables). `load_env_file()` charge un `.env` si on le souhaite.
`comparer(a, b)` fonctionne sur des objets `Personne` en mémoire, sans base.

### Le modèle `Personne`

| Champ | Contenu |
| --- | --- |
| `tree_id`, `person_id` | arbre (`gedcom_id`) et identifiant (xref) |
| `nom_complet`, `nom_norm` | premier nom principal (NAME), et sa forme normalisée |
| `prenoms`, `nom_famille` | parties du nom (GIVN / SURN), vides si inconnues |
| `noms_alternatifs` | autres noms (autres NAME, `_AKA`, `_MARNM`...) |
| `sexe` | `M`, `F` ou `U` |
| `faits` | année par fait : `BIRT`, `BAPM`, `CHR`, `DEAT`, `BURI` |
| `dates`, `lieux` | date complète (texte GEDCOM, ex. `ABT 12 MAR 1745`) et lieu, par fait |
| `mariages` | `{annee, conjoint, conjoint_norm, conjoint_id, date, lieu}` |
| `parents`, `enfants`, `conjoints` | `Proche` : `{nom, nom_norm, naissance, person_id}` |

`person_id` (dans `Proche`) et `conjoint_id` (dans `Mariage`) relient les
personnes d'un même arbre : on peut reconstruire le graphe familial à partir
des `Personne` chargées.

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


Le code est dans `src/genealogie_acadienne/`, en trois couches. Les dépendances
vont dans un seul sens : `commun` ← `donnees` ← `pipeline`.

| Fichier                            | Rôle                                                                                          |
| ---------------------------------- | --------------------------------------------------------------------------------------------- |
| `__init__.py`                      | API publique du paquet (connexion, `Personne`, chargement, noms, comparaison).                |
| **`commun/`**                      | **Fonctions pures** : aucune base, aucune entrée/sortie, ni pandas ni pymysql à l'import.    |
| `commun/modele.py`                 | Modèle `Personne` (+ `Mariage`, `Proche`, `Faits`).                                           |
| `commun/gedcom.py`                 | `evenements_gedcom` : date complète + lieu des événements, lus dans le GEDCOM brut.          |
| `commun/noms.py`                   | `normaliser`, noms partagés entre arbres (`trouver_noms_partages`), alias « dit » (`alias_dit`) et appariement par prénoms partagés (`trouver_paires`). |
| `commun/comparaison.py`            | Compare **deux** personnes et renvoie un rapport (métriques + verdicts).                      |
| `commun/criteres.py`               | Verdicts qui comptent comme concordance, et `criteres_concordants`.                           |
| `commun/variantes.py`              | Formes canoniques des prénoms (Marie / Mary) et clés orthographiques des noms de famille (Comeau / Comeaux), alias « dit » comme noms de famille. |
| `commun/candidats.py`              | Candidats par nom « relâché » : même clé de nom de famille et au moins un prénom canonique en commun (`IndexCandidats`). |
| `commun/dates.py`                  | Dates GEDCOM (ABT, BEF, AFT, BET…AND) : lecture, écart en années, décalage. |
| `commun/voisinage.py`              | Liens familiaux typés (`parent_de`, `enfant_de`, `conjoint_de`) et voisinage à k sauts. |
| `commun/clonage.py`                | Copier une personne et sa famille dans un autre arbre (doublons connus pour l'évaluation). |
| `commun/synthetique.py`            | Population acadienne synthétique multi-arbres, avec la vérité terrain des doublons. |
| **`donnees/`**                     | **Accès à la base** WebTrees.                                                                 |
| `donnees/db.py`                    | Connexion (`DBConfig`, variables d'environnement, `.env` optionnel) et utilitaires SQL.       |
| `donnees/noms.py`                  | Charge tous les noms (en écartant les arbres de `ARBRES_IGNORES`).                            |
| `donnees/personnes.py`             | Charge des `Personne` depuis la base (une personne, ou des milliers en lots).                 |
| `donnees/instantane.py`            | Instantanés Parquet : exporter toute la base une fois (`instantane_depuis_base`), puis relire les `Personne` sans base. |
| `donnees/export_parquet.py`        | Exporte les tables brutes d'une base en Parquet (une table par fichier), sans les tables d'utilisateurs. |
| `donnees/mariadb_local.py`         | Serveur MariaDB temporaire et privé (version portable téléchargée au besoin) pour importer un dump. |
| **`pipeline/`**                    | **Les tâches de ce dépôt** (points d'entrée).                                                 |
| `pipeline/apparier_personnes.py`   | Trouve les doublons et enregistre les paires dans `person_comparisons`.                       |
| `pipeline/noms_partages.py`        | Exporte un résumé des noms partagés (`temp/partages_resume.csv`).                             |
| `pipeline/comparer_paire.py`       | Charge et compare une paire précise (exemple / débogage).                                     |
| `pipeline/statistiques.py`         | Statistiques générales (durée de vie, âges, etc.). Lecture seule.                             |
| `pipeline/trouver_erreurs.py`      | Repère les erreurs de saisie (dates impossibles, etc.). Lecture seule.                        |
| `pipeline/exporter_sql.py`         | Convertit un dump `.sql` en fichiers Parquet (`genealogie-export-sql`).                       |
| `tests/`                           | Tests `pytest` (aucune base de données nécessaire).                                           |
| `documents/`                       | Notes et questions de travail.                                                                |
| `rapports/`                        | Sorties générées par les scripts.                                                             |




## Exécution

Après `uv sync`, avec le `.env` configuré, depuis la racine du dépôt (les
fichiers de sortie sont écrits dans le dossier courant). Préfixer chaque commande
par `uv run` (ou activer `.venv`) :

```bash
# Trouver les doublons -> écrit dans la table `person_comparisons`
genealogie-apparier
# ou : python -m genealogie_acadienne.pipeline.apparier_personnes

# Statistiques (lecture seule) -> rapports/statistiques.md
genealogie-statistiques
# ou : python -m genealogie_acadienne.pipeline.statistiques

# Détection d'erreurs de saisie (lecture seule) -> erreurs_a_corriger.txt
genealogie-erreurs
# ou : python -m genealogie_acadienne.pipeline.trouver_erreurs

# Autres tâches
python -m genealogie_acadienne.pipeline.noms_partages    # -> temp/partages_resume.csv
python -m genealogie_acadienne.pipeline.comparer_paire   # compare une paire d'exemple

# Tests (aucune base nécessaire)
uv run pytest
```

`apparier_personnes.py` crée la table `person_comparisons` si besoin, télécharge
en lot toutes les personnes qui partagent un nom, les compare deux à deux, et
enregistre chaque paire ayant au moins un critère concordant.

### Convertir un dump `.sql` en Parquet

Pour travailler sans base de données : on convertit une fois le dump, puis on lit
les fichiers avec pandas ou DuckDB.

```bash
uv run genealogie-export-sql chemin/dump.sql chemin/parquet/
```

- MariaDB n'a pas besoin d'être installé : s'il n'est pas dans le PATH, la version
  portable officielle (Linux x86_64 ou Windows x64, ~360 Mo, vérifiée par SHA-256)
  est téléchargée une fois dans `.mariadb/` à côté du dump (`--cache` pour changer).
  Sur macOS : `brew install mariadb`, ou `--mariadb <dossier>`.
- Un serveur temporaire (local seulement, mot de passe aléatoire) importe le dump,
  puis il est arrêté et sa base supprimée (`--garder-base` pour la garder).
- Sortie : un `<table>.parquet` par table et un `manifeste.json` (source et sa
  somme SHA-256, lignes et colonnes par table, version du paquet).
- Les tables d'utilisateurs, de sessions, de journaux et de configuration de
  WebTrees ne sont jamais exportées par défaut (`TABLES_EXCLUES`). `--tables` et
  `--exclure` pour choisir autrement, `--ecraser` pour remplacer un export.

Relire avec `lire_table` plutôt que `pd.read_parquet` seul : une colonne d'entiers
avec des valeurs vides (ex. `wt_place_location.parent_id`) reste en entiers
(`Int64`, `<NA>`) au lieu de devenir des décimaux (`12.0`, `NaN`).

```python
from genealogie_acadienne.donnees import lire_table
lieux = lire_table("chemin/parquet", "wt_place_location")
individus = lire_table("chemin/parquet", "wt_individuals", colonnes=["i_id", "i_file", "i_sex"])
```

## Les Prochaines Étapes
### Où on est en ce moment
Maintenant, ces scripts marchent pour trouver les paires d'individus qui sont peut-être les même, basé sur les critère de naissance, décès, sepulture, batpême, enfants, parents, et mariages. Les scripts sont très vite, et peut examiner une base de 150.000 individus, trouver 600.000 paires qui partagent un nom, les analyser, et présenter celles qui partagent les critères -- en moins d'une minute.

On cherche les individus qui ont exactement les mêmes noms. On ne cherche pas les variantes orthographiques ni les homonymes. 

`trouver_paires` (dans `commun/noms.py`) ajoute un appariement par prénoms partagés, alias « dit » compris (ex. « Marie Louise Comeaux » ~ « Louise Comeaux ») ; il n'est pas encore branché dans `apparier_personnes.py`.

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