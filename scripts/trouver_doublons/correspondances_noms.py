"""
Trouver les noms partagés entre plusieurs arbres.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from db import run_query, t

if TYPE_CHECKING:
    import pandas as pd
    from pymysql.connections import Connection

# Arbres à exclure de toutes les recherches. La casse est ignorée.
ARBRES_IGNORES = ["FAMILLES.ACADIENNES", "BABIN_TEST", "MY_PROJECT"]

def ids_arbres_ignores(
    conn: Connection | None = None, noms: list[str] = ARBRES_IGNORES
) -> list[int]:
    """Renvoie les `gedcom_id` des arbres à ignorer, d'après leur nom."""
    if not noms:
        return []
    g = run_query("SELECT gedcom_id, gedcom_name FROM " + t("gedcom"), conn=conn)
    # comparaison insensible à la casse : la base peut stocker « babin_test »
    noms_norm = {n.casefold() for n in noms}
    masque = g["gedcom_name"].str.casefold().isin(noms_norm)
    return g.loc[masque, "gedcom_id"].tolist()


def normaliser(texte: str | None) -> str:
    """Minuscules, sans accents ni ponctuation, espaces compactés."""
    if texte is None:
        return ""
    texte = unicodedata.normalize("NFKD", str(texte))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.lower()
    texte = "".join(c if c.isalnum() or c.isspace() else " " for c in texte)
    return " ".join(texte.split())


def charger_personnes(conn: Connection | None = None) -> pd.DataFrame:
    """Charge toutes les personnes : arbre, identifiant, nom complet."""
    df = run_query(
        f"""
        SELECT n_file AS tree_id,
               n_id   AS person_id,
               TRIM(REPLACE(n_full, '/', '')) AS nom_complet
        FROM `{t('name')}`
        WHERE n_type = 'NAME'
        """,
        conn=conn,
    )
    df = df.drop_duplicates(subset=["tree_id", "person_id"]).reset_index(drop=True)

    ignores = ids_arbres_ignores(conn)
    if ignores:
        avant = len(df)
        df = df[~df["tree_id"].isin(ignores)].reset_index(drop=True)
        print(f"{avant - len(df)} personnes ignorées "
              f"(arbres {', '.join(ARBRES_IGNORES)}).")

    df["nom_norm"] = df["nom_complet"].map(normaliser)
    return df

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

def exporter_resume(partages: pd.DataFrame, fichier: str = "temp/partages_resume.csv") -> None:
    """Écrit un résumé : une ligne par nom partagé (groupe)."""
    resume = (partages.groupby("groupe_id")
              .agg(nom_norm=("nom_norm", "first"),
                   n_personnes=("n_personnes", "first"),
                   n_arbres=("n_arbres", "first"))
              .reset_index())
    resume.to_csv(fichier, index=False, encoding="utf-8")
    print(f"{len(resume)} noms partagés -> {fichier}")


if __name__ == "__main__":
    df = charger_personnes()
    print(f"{len(df)} personnes chargées.\n")

    partages = trouver_noms_partages(df)
    exporter_resume(partages)
