"""
Modèle `Personne` : nom, sexe, faits datés, mariages, parents, enfants, conjoints.

Module pur (bibliothèque standard seulement) : on peut construire des `Personne`
à la main, sans base de données. Le chargement depuis la base est dans
`donnees/personnes.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

# --- Types des structures de données ---------------------------------------
# Faits datés d'une personne : {"BIRT": 1700, "DEAT": 1750, ...} (année ou None).
Faits = dict[str, "int | None"]


class Mariage(TypedDict):
    """Un mariage : année (ou None) et nom du conjoint (normalisé)."""
    annee: int | None
    conjoint: str | None
    conjoint_norm: str | None


class Proche(TypedDict):
    """Un proche (parent, enfant, conjoint) réduit au nom + année de naissance."""
    nom: str
    nom_norm: str
    naissance: int | None


@dataclass
class Personne:
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

    def __str__(self):
        return (f"{self.nom_complet} (arbre {self.tree_id}, id {self.person_id})")
