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

Appariement par prénoms (`trouver_paires`) : on regroupe par NOM DE FAMILLE, puis
on compare les ENSEMBLES de prénoms (alias « dit ... » compris). Ça retrouve
« Marie Louise Comeaux » ~ « Louise Comeaux » (prénom principal omis).

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


# --- Prénoms et alias « dit » ----------------------------------------------

# Mots à ne pas compter comme prénom : marqueurs d'alias (« dit Rose » -> on garde
# « rose » mais pas « dit »/« dite ») et le connecteur « ou » (« dit X ou Y »).
MARQUEURS_ALIAS = {"dit", "dite", "dits", "dites"}
CONNECTEURS_ALIAS = {"ou"}


def alias_dit(nom_complet: str | None) -> list[str]:
    """Les alias « dit » d'un nom, normalisés, dans l'ordre.

    Exemples :
      « Jean Doucet dit Laverdure »          -> ["laverdure"]
      « Marie Bourgeois dite Clarisse ou Rose » -> ["clarisse", "rose"]
      « Pierre Babin dit La Grange »         -> ["la grange"]
    """
    mots = normaliser(nom_complet).split()
    alias: list[str] = []
    courant: list[str] | None = None
    for mot in mots:
        if mot in MARQUEURS_ALIAS or (mot in CONNECTEURS_ALIAS and courant is not None):
            if courant:
                alias.append(" ".join(courant))
            courant = []
        elif courant is not None:
            courant.append(mot)
    if courant:
        alias.append(" ".join(courant))
    return alias


def tokens_prenoms(nom_complet: str | None, surn_norm: str) -> frozenset[str]:
    """Ensemble des prénoms + alias d'une personne (nom de famille exclu).

    - on part du nom complet normalisé (« Marie Clorisse Bourgeois dite Clarisse ») ;
    - on enlève les mots du nom de famille (« bourgeois ») ;
    - on enlève les marqueurs d'alias (« dit », « dite »...) et « ou », mais on
      garde l'alias lui-même (« clarisse ») ;
    - on enlève les fragments d'une seule lettre issus des élisions
      (d'Azy -> « d », l'aîné -> « l »).

    Exemple : ("Marie Bourgeois dite Rose", "bourgeois") -> {"marie", "rose"}
    """
    surn = set(normaliser(surn_norm).split())
    return frozenset(
        mot for mot in normaliser(nom_complet).split()
        if len(mot) > 1 and mot not in surn
        and mot not in MARQUEURS_ALIAS and mot not in CONNECTEURS_ALIAS
    )


# Seuil minimal de prénoms en commun pour chaque type d'appariement.
# Les paires aux prénoms IDENTIQUES sont toujours gardées (exact=True) ;
# "partage2" / "partage1" y ajoutent les paires qui partagent au moins 2 / 1 prénoms.
SEUILS_PARTAGE = {"exact": None, "partage2": 2, "partage1": 1}

COLONNES_PAIRES = ["tree_id_a", "person_id_a", "tree_id_b", "person_id_b",
                   "nom_famille", "nom_a", "nom_b", "n_communs",
                   "prenoms_communs", "exact"]


def _ligne_paire(a, b, communs: frozenset[str], exact: bool) -> dict:
    """Une ligne de sortie pour une paire, dans l'ordre canonique (arbre, id)."""
    if (int(a.tree_id), str(a.person_id)) > (int(b.tree_id), str(b.person_id)):
        a, b = b, a
    return {
        "tree_id_a": a.tree_id, "person_id_a": a.person_id,
        "tree_id_b": b.tree_id, "person_id_b": b.person_id,
        "nom_famille": a.surn_norm,
        "nom_a": a.nom_complet, "nom_b": b.nom_complet,
        "n_communs": len(communs),
        "prenoms_communs": " ".join(sorted(communs)),
        "exact": exact,
    }


def trouver_paires(
    df: pd.DataFrame, type_appariement: str = "exact", entre_arbres: bool = True
) -> pd.DataFrame:
    """Paires de personnes qui portent (au moins en partie) le même nom.

    `df` : colonnes tree_id, person_id, nom_complet, nom_famille
    (voir `donnees.noms.charger_personnes`).

    On regroupe par NOM DE FAMILLE normalisé, puis on apparie les PRÉNOMS
    (alias « dit ... » compris) selon `type_appariement` :
      - "exact"    : mêmes prénoms exactement (ordre ignoré) ;
      - "partage2" : + les paires qui ont au moins 2 prénoms en commun ;
      - "partage1" : + les paires qui ont au moins 1 prénom en commun.

    `entre_arbres=True` : on ignore les paires du même arbre.

    Renvoie un DataFrame trié : les paires exactes d'abord, puis par nombre de
    prénoms en commun décroissant.
    """
    import pandas as pd  # pandas seulement à l'appel : `commun` reste pur à l'import

    if type_appariement not in SEUILS_PARTAGE:
        raise ValueError(f"type_appariement inconnu : {type_appariement!r} "
                         f"(choix : {', '.join(SEUILS_PARTAGE)})")
    seuil = SEUILS_PARTAGE[type_appariement]

    travail = df.copy()
    travail["surn_norm"] = travail["nom_famille"].map(normaliser)
    travail["prenoms"] = [
        tokens_prenoms(nc, sn)
        for nc, sn in zip(travail["nom_complet"], travail["surn_norm"])
    ]
    travail = travail[(travail["surn_norm"] != "") & (travail["prenoms"].map(len) > 0)]

    lignes = []
    for _, bloc in travail.groupby("surn_norm"):
        par_prenoms: dict[frozenset[str], list] = {}
        for personne in bloc.itertuples(index=False):
            par_prenoms.setdefault(personne.prenoms, []).append(personne)
        ensembles = list(par_prenoms)

        for i, sa in enumerate(ensembles):
            membres_a = par_prenoms[sa]
            # (1) même ensemble de prénoms -> correspondance exacte
            for j, a in enumerate(membres_a):
                for b in membres_a[j + 1:]:
                    if not (entre_arbres and a.tree_id == b.tree_id):
                        lignes.append(_ligne_paire(a, b, sa, exact=True))
            if seuil is None:
                continue
            # (2) ensembles différents qui partagent assez de prénoms
            for sb in ensembles[i + 1:]:
                communs = sa & sb
                if len(communs) < seuil:
                    continue
                for a in membres_a:
                    for b in par_prenoms[sb]:
                        if not (entre_arbres and a.tree_id == b.tree_id):
                            lignes.append(_ligne_paire(a, b, communs, exact=False))

    paires = pd.DataFrame(lignes, columns=COLONNES_PAIRES)
    return paires.sort_values(
        ["exact", "n_communs", "nom_famille", "tree_id_a", "person_id_a", "tree_id_b", "person_id_b"],
        ascending=[False, False, True, True, True, True, True],
    ).reset_index(drop=True)
