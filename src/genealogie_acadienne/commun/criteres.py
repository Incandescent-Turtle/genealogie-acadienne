"""
Critères concordants : quelles métriques d'une comparaison comptent comme
une « concordance » entre deux personnes.

Avec la correspondance exacte des noms (`noms.py`), c'est la méthode de base :
on compte les critères concordants d'une paire. Module pur.
"""

from __future__ import annotations

from .comparaison import RapportComplet

# Pour chaque métrique, les verdicts qui comptent comme une "concordance".
# (voir comparaison.py pour la liste des verdicts possibles)
VERDICTS_POSITIFS = {
    "naissance": {"identique", "proche"},
    "bapteme": {"identique", "proche"},
    "deces": {"identique", "proche"},
    "sepulture": {"identique", "proche"},
    "mariage": {"identique", "proche", "meme_conjoint"},
    # "periode_estimee": {"chevauchement", "proche"}, # ça aide à idenifier, mais c'est créé par rapport aux dates connues, qui sont déjà les autres métriques.
    "ascendants": {"communs"},
    "descendants": {"communs"},
}


def criteres_concordants(rapport: RapportComplet) -> list[str]:
    """Liste des métriques où les deux personnes concordent."""
    concordants = []
    for nom, r in rapport.items():
        if r["verdict"] in VERDICTS_POSITIFS.get(nom, set()):
            concordants.append(nom)
    return concordants
