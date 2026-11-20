"""
Trouver les noms partagés entre plusieurs arbres.

Première étape du pipeline : repérer les personnes qui pourraient être des doublons parce qu'elles portent le même nom dans des arbres différents.

Étapes :
  1. `donnees.noms.charger_personnes` lit tous les noms (table `name`), écarte
     les arbres de `ARBRES_IGNORES` et normalise chacun avec `normaliser`
     (minuscules, sans accents ni ponctuation) ;
  2. `trouver_noms_partages` regroupe par nom normalisé et garde les noms
     présents dans au moins 2 arbres (chaque groupe reçoit un `groupe_id`).

Module pur : il travaille sur un DataFrame déjà chargé, sans base de données.

Ici, on rapproche les noms de façon EXACTE (après normalisation) : deux graphies différentes du même nom ne se rencontrent pas encore.

À ajouter :
  - rapprocher les noms proches : homophones, fautes de frappe, deuxièmes
    prénoms (RapidFuzz ou comparaison phonétique)
  - gérer les noms à particule ou les noms de famille multiples
  - regarder aussi les personnes dans le même arbre
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def normaliser(texte: str | None) -> str:
    """Minuscules, sans accents ni ponctuation, espaces compactés."""
    if texte is None:
        return ""
    texte = unicodedata.normalize("NFKD", str(texte))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.lower()
    texte = "".join(c if c.isalnum() or c.isspace() else " " for c in texte)
    return " ".join(texte.split())


def chercher_meme_nom(df: pd.DataFrame, nom_complet: str, tree_id: int) -> pd.DataFrame:
    """Renvoie les personnes de l'arbre `tree_id` au nom exactement identique."""
    cible = normaliser(nom_complet)
    sous = df[df["tree_id"] == tree_id]
    return sous[sous["nom_norm"] == cible]


def trouver_noms_partages(
    df: pd.DataFrame, min_personnes: int = 2, min_arbres: int = 2
) -> pd.DataFrame:
    """Renvoie toutes les personnes qui partagent leur nom avec d'autres. On regroupe par nom normalisé."""
    df = df[df["nom_norm"] != ""].copy()
    groupes = df.groupby("nom_norm")
    df["n_personnes"] = groupes["person_id"].transform("size")
    df["n_arbres"] = groupes["tree_id"].transform("nunique")

    masque = (df["n_personnes"] >= min_personnes) & (df["n_arbres"] >= min_arbres)
    partages = df[masque].copy()

    ordre = (partages.groupby("nom_norm")["person_id"].size()
             .sort_values(ascending=False).reset_index(name="taille"))
    ordre["groupe_id"] = range(1, len(ordre) + 1)
    partages = partages.merge(ordre[["nom_norm", "groupe_id"]], on="nom_norm")

    partages = partages.sort_values(["groupe_id", "tree_id", "person_id"])
    colonnes = ["tree_id", "person_id", "nom_complet", "nom_norm",
                "n_personnes", "n_arbres", "groupe_id"]
    return partages[colonnes].reset_index(drop=True)
