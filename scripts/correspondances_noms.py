"""
Trouver les noms partagés entre plusieurs arbres.
"""

import argparse
import unicodedata
from itertools import combinations

import pandas as pd

from db import run_query, t

# Arbres à exclure de toutes les recherches. La casse est ignorée.
ARBRES_IGNORES = ["FAMILLES.ACADIENNES", "BABIN_TEST", "MY_PROJECT"]

# Mots à ne pas compter comme prénom : marqueurs d'alias (« dit Rose » -> on garde
# « rose » mais pas « dit »/« dite ») et le connecteur « ou » (« dit X ou Y »).
MARQUEURS_ALIAS = {"dit", "dite", "dits", "dites", "ou"}

def ids_arbres_ignores(conn=None, noms=ARBRES_IGNORES):
    """Renvoie les `gedcom_id` des arbres à ignorer, d'après leur nom."""
    if not noms:
        return []
    g = run_query("SELECT gedcom_id, gedcom_name FROM " + t("gedcom"), conn=conn)
    # comparaison insensible à la casse : la base peut stocker « babin_test »
    noms_norm = {n.casefold() for n in noms}
    masque = g["gedcom_name"].str.casefold().isin(noms_norm)
    return g.loc[masque, "gedcom_id"].tolist()


def normaliser(texte):
    """Minuscules, sans accents ni ponctuation, espaces compactés."""
    if texte is None:
        return ""
    texte = unicodedata.normalize("NFKD", str(texte))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.lower()
    texte = "".join(c if c.isalnum() or c.isspace() else " " for c in texte)
    return " ".join(texte.split())


def tokens_prenoms(nom_complet, surn_norm):
    """Ensemble des prénoms + alias d'une personne (nom de famille exclu).

    - on part du nom complet normalisé (« Marie Clorisse Bourgeois dite Clarisse ») ;
    - on enlève les mots du nom de famille (« bourgeois ») ;
    - on enlève les marqueurs d'alias (« dit », « dite »...) mais on garde l'alias
      lui-même (« clarisse »).

    Exemple : ("Marie Bourgeois dite Rose", "bourgeois") -> {"marie", "rose"}
    """
    surn = set(surn_norm.split())
    return frozenset(
        mot for mot in normaliser(nom_complet).split()
        # on ignore le nom de famille, les marqueurs d'alias, et les fragments
        # d'une seule lettre issus des élisions (d'Azy -> « d », l'aîné -> « l »).
        if len(mot) > 1 and mot not in surn and mot not in MARQUEURS_ALIAS
    )


def charger_personnes(conn=None):
    """Charge toutes les personnes : arbre, identifiant, nom complet, nom de famille."""
    df = run_query(
        f"""
        SELECT n_file AS tree_id,
               n_id   AS person_id,
               TRIM(REPLACE(n_full, '/', '')) AS nom_complet,
               n_surn AS nom_famille
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

def chercher_meme_nom(df, nom_complet, tree_id):
    """Renvoie les personnes de l'arbre `tree_id` au nom exactement identique."""
    cible = normaliser(nom_complet)
    sous = df[df["tree_id"] == tree_id]
    return sous[sous["nom_norm"] == cible]


def trouver_noms_partages(df, min_personnes=2, min_arbres=2):
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

def exporter_resume(partages, fichier="temp/partages_resume.csv"):
    """Écrit un résumé : une ligne par nom partagé (groupe)."""
    resume = (partages.groupby("groupe_id")
              .agg(nom_norm=("nom_norm", "first"),
                   n_personnes=("n_personnes", "first"),
                   n_arbres=("n_arbres", "first"))
              .reset_index())
    resume.to_csv(fichier, index=False, encoding="utf-8")
    print(f"{len(resume)} noms partagés -> {fichier}")


# Seuil minimal de prénoms en commun pour chaque type d'appariement.
# "exact" est traité à part : les ensembles de prénoms doivent être identiques.
SEUILS_PARTAGE = {"exact": None, "partage2": 2, "partage1": 1}


def _canoniser(a, b):
    """Ordonne une paire de personnes par (arbre, identifiant) pour éviter les doublons."""
    if (int(a.tree_id), str(a.person_id)) <= (int(b.tree_id), str(b.person_id)):
        return a, b
    return b, a


def _ligne_paire(a, b, communs, exact):
    """Une ligne de sortie pour une paire de personnes."""
    a, b = _canoniser(a, b)
    return {
        "tree_id_a": a.tree_id, "person_id_a": a.person_id,
        "tree_id_b": b.tree_id, "person_id_b": b.person_id,
        "nom_famille": a.surn_norm,
        "nom_a": a.nom_complet, "nom_b": b.nom_complet,
        "n_communs": len(communs),
        "prenoms_communs": " ".join(sorted(communs)),
        "exact": exact,
    }


def trouver_paires(df, type_appariement="exact", entre_arbres=True):
    """Paires de personnes qui portent (au moins en partie) le même nom.

    On regroupe toujours par NOM DE FAMILLE normalisé, puis on apparie les
    PRÉNOMS (alias « dit ... » compris) selon `type_appariement` :
      - "exact"    : mêmes prénoms exactement (ordre ignoré) ;
      - "partage2" : au moins 2 prénoms en commun ;
      - "partage1" : au moins 1 prénom en commun.

    `entre_arbres=True` : on ignore les paires du même arbre.

    Renvoie un DataFrame trié : les paires exactes d'abord, puis par nombre de
    prénoms en commun décroissant.
    """
    if type_appariement not in SEUILS_PARTAGE:
        raise ValueError(f"type_appariement inconnu : {type_appariement!r} "
                         f"(choix : {', '.join(SEUILS_PARTAGE)})")
    seuil = SEUILS_PARTAGE[type_appariement]
    exact_seul = type_appariement == "exact"

    # Préparer nom de famille normalisé + ensemble de prénoms (avec alias).
    travail = df.copy()
    travail["surn_norm"] = travail["nom_famille"].map(normaliser)
    travail["prenoms"] = [
        tokens_prenoms(nc, sn)
        for nc, sn in zip(travail["nom_complet"], travail["surn_norm"])
    ]
    travail = travail[(travail["surn_norm"] != "") & (travail["prenoms"].map(len) > 0)]

    lignes = []
    for _, bloc in travail.groupby("surn_norm"):
        # regrouper les personnes par ensemble de prénoms identique
        par_prenoms = {}
        for personne in bloc.itertuples(index=False):
            par_prenoms.setdefault(personne.prenoms, []).append(personne)
        ensembles = list(par_prenoms.keys())

        for i, sa in enumerate(ensembles):
            membres_a = par_prenoms[sa]
            # (1) même ensemble de prénoms -> correspondance exacte
            if exact_seul or len(sa) >= seuil:
                for a, b in combinations(membres_a, 2):
                    if entre_arbres and a.tree_id == b.tree_id:
                        continue
                    lignes.append(_ligne_paire(a, b, sa, exact=True))
            if exact_seul:
                continue
            # (2) ensembles différents qui partagent assez de prénoms
            for sb in ensembles[i + 1:]:
                communs = sa & sb
                if len(communs) < seuil:
                    continue
                for a in membres_a:
                    for b in par_prenoms[sb]:
                        if entre_arbres and a.tree_id == b.tree_id:
                            continue
                        lignes.append(_ligne_paire(a, b, communs, exact=False))

    colonnes = ["tree_id_a", "person_id_a", "tree_id_b", "person_id_b",
                "nom_famille", "nom_a", "nom_b", "n_communs",
                "prenoms_communs", "exact"]
    paires = pd.DataFrame(lignes, columns=colonnes)
    # tri : exactes d'abord, puis le plus de prénoms en commun
    paires = paires.sort_values(
        ["exact", "n_communs", "nom_famille"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    return paires


def exporter_paires(paires, fichier="temp/paires_noms.csv"):
    """Écrit les paires appariées (déjà triées) dans un CSV."""
    paires.to_csv(fichier, index=False, encoding="utf-8")
    print(f"{len(paires)} paires -> {fichier}")


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(
        description="Apparie les personnes par nom (avec ou sans 2e prénoms)."
    )
    analyseur.add_argument("--type", default="exact", choices=list(SEUILS_PARTAGE),
                           help="exact | partage2 (>=2 prénoms) | partage1 (>=1 prénom)")
    analyseur.add_argument("--sortie", default="temp/paires_noms.csv",
                           help="fichier CSV de sortie")
    analyseur.add_argument("--meme-arbre", action="store_true",
                           help="inclure aussi les paires du même arbre")
    args = analyseur.parse_args()

    df = charger_personnes()
    print(f"{len(df)} personnes chargées.\n")

    paires = trouver_paires(df, type_appariement=args.type,
                            entre_arbres=not args.meme_arbre)
    n_exactes = int(paires["exact"].sum())
    print(f"Type « {args.type} » : {len(paires)} paires "
          f"({n_exactes} exactes, {len(paires) - n_exactes} partielles).")
    exporter_paires(paires, args.sortie)
