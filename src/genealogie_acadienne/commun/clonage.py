"""
Copier une personne et sa famille dans un autre arbre (clonage).

Sert à fabriquer des doublons CONNUS : on copie une personne bien documentée
et ses proches dans un arbre fictif, on modifie la copie, et on sait que la
copie et l'original sont la même personne (vérité terrain).

  - `score_documentation` : nombre de champs remplis d'une personne ;
  - `taille_famille` : nombre de proches présents dans l'arbre ;
  - `choisir_bien_documentees` : tirage (avec graine) de personnes bien documentées ;
  - `cloner_famille` : copie d'une personne + ses proches à `profondeur` sauts,
    avec de nouveaux identifiants, dans l'arbre `tree_id`.

Module pur : aucune base.
"""

from __future__ import annotations

import copy
import random
from collections.abc import Mapping

from .modele import Personne
from .voisinage import Cle, cle, construire_adjacence, voisinage

FAITS_DATES = ("BIRT", "BAPM", "DEAT", "BURI")


def score_documentation(p: Personne) -> int:
    """Nombre de champs remplis : faits datés, année de mariage, prénom, nom de famille."""
    n = sum(1 for f in FAITS_DATES if p.faits.get(f))
    n += any(m.get("annee") for m in p.mariages)
    n += bool(p.prenoms or len(p.nom_complet.split()) > 1)
    n += bool(p.nom_famille)
    return n


def taille_famille(p: Personne, index: Mapping[Cle, Personne]) -> int:
    """Nombre de proches (parents, conjoints, enfants) présents dans l'index."""
    ids = {x.get("person_id") for x in p.parents + p.conjoints + p.enfants}
    return sum(1 for x in ids if x and (p.tree_id, x) in index)


def choisir_bien_documentees(
    index: Mapping[Cle, Personne], n: int, rng: random.Random,
    min_champs: int, min_famille: int, exclure: set[Cle] = frozenset(),
) -> list[Cle]:
    """Tire jusqu'à `n` personnes avec au moins `min_champs` champs remplis ET
    `min_famille` proches dans l'arbre. Le résultat ne dépend que de `rng`
    (jamais de l'ordre du dictionnaire) ; il est trié par clé."""
    eligibles = sorted(
        k for k, p in index.items()
        if k not in exclure and score_documentation(p) >= min_champs
        and taille_famille(p, index) >= min_famille
    )
    return sorted(rng.sample(eligibles, min(n, len(eligibles))))


def cloner_famille(
    depart: Cle, index: Mapping[Cle, Personne], tree_id: int, prefixe: str,
    profondeur: int = 1, adjacence=None,
) -> tuple[dict[Cle, Personne], Cle]:
    """Copie `depart` et tous ceux à au plus `profondeur` sauts dans l'arbre `tree_id`.

    Renvoie ({clé originale: copie}, clé de la copie de `depart`). Les nouveaux
    identifiants sont `prefixe` + numéro (le départ reçoit le numéro 0). Les proches
    qui ne sont pas copiés disparaissent des listes des copies, et chaque
    `person_id` / `conjoint_id` est renuméroté. Les originaux ne sont pas modifiés.
    """
    if adjacence is None:
        adjacence = construire_adjacence(index)
    membres = sorted(voisinage(depart, index, profondeur, adjacence),
                     key=lambda k: (k != depart, k))
    nouvel_id = {k[1]: f"{prefixe}{n}" for n, k in enumerate(membres)}
    copies: dict[Cle, Personne] = {}
    for k in membres:
        p = copy.deepcopy(index[k])
        p.tree_id, p.person_id = tree_id, nouvel_id[k[1]]
        for role in ("parents", "enfants", "conjoints"):
            setattr(p, role, [dict(x, person_id=nouvel_id[x["person_id"]])
                              for x in getattr(p, role) if x.get("person_id") in nouvel_id])
        p.mariages = [dict(m, conjoint_id=nouvel_id[m["conjoint_id"]]) for m in p.mariages
                      if m.get("conjoint_id") in nouvel_id]
        copies[k] = p
    return copies, cle(copies[depart])
