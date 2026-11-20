"""
Outils pour trouver les personnes en double entre les arbres d'une base WebTrees.

Importer ce paquet n'ouvre aucune connexion et ne lit aucun fichier `.env`.

Organisation (les dépendances vont dans un seul sens : commun <- donnees <- pipeline) :
  - `commun`   : fonctions pures (modèle, noms, comparaison, critères)
  - `donnees`  : accès à la base (connexion, chargement)
  - `pipeline` : les tâches de ce dépôt (non réexportées ici)

API publique :
  - connexion   : DBConfig, get_connection, load_env_file, set_table_prefix
  - modèle      : Personne, Mariage, Proche, Faits
  - chargement  : charger_personnes (noms -> DataFrame), charger_groupe, charger_personne
  - noms        : normaliser, trouver_noms_partages, chercher_meme_nom,
                  alias_dit, tokens_prenoms, trouver_paires (par prénoms partagés)
  - comparaison : comparer (deux Personne en mémoire), criteres_concordants, VERDICTS_POSITIFS
  - GEDCOM      : evenements_gedcom (date + lieu des événements d'un GEDCOM brut)
  - instantanés : ecrire_instantane, lire_instantane, instantane_depuis_base (Parquet)
Les autres outils (variantes, candidats, dates, voisinage, clonage, synthétique)
sont dans `genealogie_acadienne.commun`.

Les noms de `donnees` sont chargés à la demande : `import genealogie_acadienne`
(ou `genealogie_acadienne.commun`) n'importe ni pandas ni pymysql.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from .commun import (
    VERDICTS_POSITIFS,
    Evenement,
    Faits,
    Mariage,
    Personne,
    Proche,
    RapportComplet,
    alias_dit,
    chercher_meme_nom,
    comparer,
    criteres_concordants,
    evenements_gedcom,
    normaliser,
    tokens_prenoms,
    trouver_noms_partages,
    trouver_paires,
)

if TYPE_CHECKING:
    from .donnees import (
        DBConfig,
        charger_groupe,
        charger_personne,
        charger_personnes,
        get_connection,
        load_env_file,
        set_table_prefix,
        ecrire_instantane,
        lire_instantane,
        instantane_depuis_base,
    )

_DONNEES = {
    "DBConfig", "get_connection", "load_env_file", "set_table_prefix",
    "charger_personnes", "charger_groupe", "charger_personne",
    "ecrire_instantane", "lire_instantane", "instantane_depuis_base",
}


def __getattr__(nom: str):
    """Charge les noms de `donnees` au premier accès (PEP 562)."""
    if nom in _DONNEES:
        valeur = getattr(importlib.import_module(".donnees", __name__), nom)
        globals()[nom] = valeur
        return valeur
    raise AttributeError(f"module {__name__!r} has no attribute {nom!r}")


def __dir__():
    return sorted(set(globals()) | _DONNEES)


__version__ = "0.1.0"

__all__ = [
    "DBConfig",
    "get_connection",
    "load_env_file",
    "set_table_prefix",
    "Personne",
    "Mariage",
    "Proche",
    "Faits",
    "charger_personnes",
    "charger_groupe",
    "charger_personne",
    "normaliser",
    "trouver_noms_partages",
    "chercher_meme_nom",
    "comparer",
    "RapportComplet",
    "criteres_concordants",
    "VERDICTS_POSITIFS",
    "evenements_gedcom",
    "Evenement",
    "alias_dit",
    "tokens_prenoms",
    "trouver_paires",
    "ecrire_instantane",
    "lire_instantane",
    "instantane_depuis_base",
]
