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