"""
Modèle `Personne` : nom, sexe, faits datés, mariages, parents, enfants, conjoints.

Module pur (bibliothèque standard seulement) : on peut construire des `Personne`
à la main, sans base de données. Le chargement depuis la base est dans
`donnees/personnes.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NotRequired, TypedDict

# --- Types des structures de données ---------------------------------------
# Faits datés d'une personne : {"BIRT": 1700, "DEAT": 1750, ...} (année ou None).
Faits = dict[str, "int | None"]


class Mariage(TypedDict):
    """Un mariage : année (ou None) et nom du conjoint (normalisé).

    `conjoint_id` est l'identifiant (xref) du conjoint dans le même arbre, ou
    None s'il est inconnu. Il est rempli par le chargement depuis la base ;
    il peut manquer dans un dictionnaire construit à la main.
    """
    annee: int | None
    conjoint: str | None
    conjoint_norm: str | None
    conjoint_id: NotRequired[str | None]


class Proche(TypedDict):
    """Un proche (parent, enfant, conjoint) réduit au nom + année de naissance.

    `person_id` est l'identifiant (xref) du proche dans le même arbre : il
    permet de relier les personnes entre elles (graphe familial). Il est rempli
    par le chargement depuis la base ; il peut manquer dans un dictionnaire
    construit à la main.
    """
    nom: str
    nom_norm: str
    naissance: int | None
    person_id: NotRequired[str]


@dataclass
class Personne:
    """Une personne d'un arbre.

    `nom_complet` est le premier nom principal (NAME) tel quel ; `prenoms` et
    `nom_famille` en sont les parties (GIVN / SURN, vides si inconnues).
    `noms_alternatifs` contient les autres noms enregistrés (autres NAME,
    _AKA, _MARNM...), sans le nom principal.
    """
    tree_id: int
    person_id: str
    nom_complet: str
    nom_norm: str
    sexe: str
    faits: Faits
    mariages: list[Mariage] = field(default_factory=list)
    parents: list[Proche] = field(default_factory=list)
    enfants: list[Proche] = field(default_factory=list)
    conjoints: list[Proche] = field(default_factory=list)
    prenoms: str = ""
    nom_famille: str = ""
    noms_alternatifs: list[str] = field(default_factory=list)

    def __str__(self):
        return (f"{self.nom_complet} (arbre {self.tree_id}, id {self.person_id})")
