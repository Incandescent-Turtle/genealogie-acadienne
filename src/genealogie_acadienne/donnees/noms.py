"""
Charger tous les noms de personnes depuis la base (table `name`).

Les arbres de `ARBRES_IGNORES` sont écartés, et chaque nom est normalisé avec
`commun.noms.normaliser`. Le regroupement des noms partagés est dans
`commun/noms.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..commun.noms import normaliser
from .db import run_query, t

if TYPE_CHECKING:
    import pandas as pd

    from .db import Connexion

# Arbres à exclure de toutes les recherches. La casse est ignorée.
# FAMILLES.ACADIENNES et BABIN_TEST sont des copies d'autres arbres, MY_PROJECT un essai.
# HANKINSON a été réimporté le 2025-03-18 avec le fichier de HARRINGTON : il contient
# les mêmes 203 personnes que HARRINGTON, qu'on garde.
ARBRES_IGNORES = ["FAMILLES.ACADIENNES", "BABIN_TEST", "MY_PROJECT", "HANKINSON"]

def ids_arbres_ignores(
    conn: Connexion | None = None, noms: list[str] = ARBRES_IGNORES
) -> list[int]:
    """Renvoie les `gedcom_id` des arbres à ignorer, d'après leur nom."""
    if not noms:
        return []
    g = run_query("SELECT gedcom_id, gedcom_name FROM " + t("gedcom"), conn=conn)
    # comparaison insensible à la casse : la base peut stocker « babin_test »
    noms_norm = {n.casefold() for n in noms}
    masque = g["gedcom_name"].str.casefold().isin(noms_norm)
    return g.loc[masque, "gedcom_id"].tolist()


def charger_personnes(conn: Connexion | None = None) -> pd.DataFrame:
    """Charge toutes les personnes : arbre, identifiant, nom complet, nom de famille."""
    df = run_query(
        f"""
        SELECT n_file AS tree_id,
               n_id   AS person_id,
               TRIM(REPLACE(n_full, '/', '')) AS nom_complet,
               n_surn AS nom_famille
        FROM `{t('name')}`
        WHERE n_type = 'NAME'
        ORDER BY n_file, n_id, n_num
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
    # WebTrees met « @N.M. » quand le nom de famille est inconnu
    df["nom_famille"] = df["nom_famille"].where(df["nom_famille"] != "@N.M.", None)
    return df
