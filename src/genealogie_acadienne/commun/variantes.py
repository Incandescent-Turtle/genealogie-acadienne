"""
Formes canoniques des prénoms et des noms de famille.

Deux graphies du même nom doivent donner la même CLÉ :
  - prénoms : table de variantes (Marie / Mary / Maria, Jean / John...) ;
  - noms de famille : règles orthographiques simples pour les finales
    acadiennes (Comeau / Comeaux, Thibodeau / Thibodeaux / Thibideau,
    Arsenault / Arseneau, Doucet / Doucette, Melanson / Melançon...).

Ce sont des HEURISTIQUES : elles rapprochent trop parfois (c'est voulu, la
génération de candidats doit être large), et elles ne remplacent pas une
vraie comparaison. Module pur : aucune base.

Voir aussi `noms.py` (`normaliser`, `alias_dit`,
`tokens_prenoms`), sur lesquels ce module s'appuie.
"""

from __future__ import annotations

import re

from .noms import alias_dit, normaliser, tokens_prenoms

# Groupes de variantes de prénoms : la première forme est la forme canonique.
# Formes françaises d'abord (la base est surtout francophone), puis anglaises,
# latines (registres) et abréviations courantes.
GROUPES_PRENOMS: list[tuple[str, ...]] = [
    ("marie", "mary", "maria", "marye"),
    ("jean", "john", "joannes", "jn"),
    ("joseph", "jos", "josephus", "joe"),
    ("pierre", "peter", "petrus", "pre"),
    ("jacques", "james", "jacob", "jacobus"),
    ("francois", "francis", "frank", "franciscus"),
    ("francoise", "frances", "fanny"),
    ("marguerite", "margaret", "margarita", "marguarite", "margot"),
    ("anne", "ann", "anna", "annie", "nancy"),
    ("elisabeth", "elizabeth", "isabelle", "isabel", "elisa", "betsy"),
    ("catherine", "katherine", "catharine", "catarina", "kate"),
    ("madeleine", "magdeleine", "madelaine", "magdalena", "madeline"),
    ("charles", "carolus", "charlie"),
    ("louis", "lewis", "ludovicus"),
    ("louise", "louisa", "eloise"),
    ("paul", "paulus"),
    ("michel", "michael", "mitchell", "michaelus"),
    ("guillaume", "william", "guilielmus", "bill"),
    ("antoine", "anthony", "antonius", "tony"),
    ("etienne", "stephen", "steven", "stephanus"),
    ("germain", "germanus"),
    ("cecile", "cecilia", "cecily"),
    ("genevieve", "genevive", "jenny"),
    ("rosalie", "rose", "rosa"),
    ("helene", "helen", "ellen", "eleanor"),
    ("jeanne", "jane", "joan", "jeannette", "jenny"),
    ("agnes", "agnez"),
    ("olivier", "oliver"),
    ("claude", "claudius"),
    ("alexis", "alexius"),
    ("simon", "simeon"),
    ("augustin", "augustine", "austin"),
    ("isidore", "isidor"),
    ("zacharie", "zachary", "zacharias"),
    ("abraham", "abram"),
    ("baptiste", "batiste", "bte"),
]

# {variante: forme canonique}
CANONIQUE_PRENOM: dict[str, str] = {
    variante: groupe[0] for groupe in GROUPES_PRENOMS for variante in groupe
}

# Règles pour les finales des noms de famille, appliquées dans l'ordre,
# sur le nom normalisé et collé (sans espaces).
REGLES_NOM_FAMILLE: list[tuple[str, str]] = [
    (r"ph", "f"),
    (r"nc", "ns"),                                   # Melançon (-> melancon) ~ Melanson
    (r"(eaux|eaud|eault|eau|aux|aud|ault|ots|ot)$", "o"),  # Comeau(x), Arsenault, Boudrot
    (r"(ette|ett)$", "et"),                          # Doucette ~ Doucet
    (r"(ie|y)$", "i"),                               # Savoie ~ Savoy, Landrie ~ Landry
    (r"e$", ""),
    (r"([a-z])\1+", r"\1"),                          # lettres doublées (Terriot ~ Theriot)
]

# Particules enlevées en tête du nom de famille (« d'Entremont » ~ « Entremont »).
# « le » / « la » font partie du nom (LeBlanc, La Rosette) : on les garde.
PARTICULES = {"de", "d", "du", "des"}


def cle_prenom(prenom: str | None) -> str:
    """Forme canonique d'UN prénom normalisé (« Mary » -> « marie »)."""
    p = normaliser(prenom).replace(" ", "")
    return CANONIQUE_PRENOM.get(p, p)


def cle_nom_famille(nom: str | None) -> str:
    """Clé orthographique d'un nom de famille (« Thibodeaux » -> « tibodo »).

    On enlève les particules en tête (« d'Entremont » -> « entremont »), on
    colle les mots, on simplifie « th » -> « t », puis on applique
    `REGLES_NOM_FAMILLE`.
    """
    mots = normaliser(nom).split()
    while len(mots) > 1 and mots[0] in PARTICULES:
        mots = mots[1:]
    cle = "".join(mots).replace("th", "t")
    for motif, remplacement in REGLES_NOM_FAMILLE:
        cle = re.sub(motif, remplacement, cle)
    return cle


def cles_prenoms(nom_complet: str | None, nom_famille: str | None) -> frozenset[str]:
    """Prénoms canoniques d'une personne (alias « dit » compris, nom de famille exclu).

    Exemple : (« Mary Louise Comeaux dite Rose », « Comeaux »)
              -> {"marie", "louise", "rosalie"}
    """
    return frozenset(cle_prenom(t) for t in tokens_prenoms(nom_complet, nom_famille or ""))


def cles_noms_famille(nom_famille: str | None, nom_complet: str | None = None) -> frozenset[str]:
    """Clés de nom de famille d'une personne : le nom lui-même, et les alias
    « dit » du nom complet (un « dit » acadien est souvent un nom de famille :
    « Jean Doucet dit Laverdure » peut apparaître comme « Jean Laverdure »)."""
    cles = {cle_nom_famille(nom_famille)} if nom_famille else set()
    for alias in alias_dit(nom_complet):
        cles.add(cle_nom_famille(alias))
    return frozenset(c for c in cles if c)


def nom_famille_probable(nom_complet: str | None, nom_famille: str | None) -> str:
    """Le nom de famille, ou à défaut le dernier mot du nom complet avant un « dit »."""
    if nom_famille:
        return nom_famille
    mots = normaliser(nom_complet).split()
    for i, mot in enumerate(mots):
        if mot in ("dit", "dite"):
            mots = mots[:i]
            break
    return mots[-1] if len(mots) > 1 else ""
