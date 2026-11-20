"""Clonage d'une famille dans un autre arbre (module pur)."""

import random

from genealogie_acadienne.commun.clonage import (
    choisir_bien_documentees, cloner_famille, score_documentation, taille_famille)
from genealogie_acadienne.commun.synthetique import generer_population
from genealogie_acadienne.commun.voisinage import indexer


def test_score_et_taille(famille):
    index = indexer(famille)
    pierre = famille[2]
    assert score_documentation(pierre) == 4          # naissance, mariage, prénom, nom de famille
    assert taille_famille(pierre, index) == 4         # 2 parents, 1 conjointe, 1 enfant


def test_choix_deterministe():
    index = indexer(generer_population(1, n_fondateurs=6, n_generations=4, n_arbres=4).personnes)
    a = choisir_bien_documentees(index, 10, random.Random(0), 3, 3)
    assert a == choisir_bien_documentees(index, 10, random.Random(0), 3, 3) and len(a) == 10
    assert all(score_documentation(index[k]) >= 3 and taille_famille(index[k], index) >= 3 for k in a)


def test_cloner_famille(famille):
    index = indexer(famille)
    copies, depart = cloner_famille((1, "I3"), index, 900, "C_")
    assert depart == (900, "C_0")
    assert set(copies) == {(1, "I1"), (1, "I2"), (1, "I3"), (1, "I5"), (1, "I6")}  # sans Anne (sœur)
    nouveaux = {(p.tree_id, p.person_id) for p in copies.values()}
    for p in copies.values():
        assert p.tree_id == 900
        for x in p.parents + p.enfants + p.conjoints:
            assert (900, x["person_id"]) in nouveaux
        for m in p.mariages:
            assert (900, m["conjoint_id"]) in nouveaux
    assert famille[2].tree_id == 1 and famille[2].person_id == "I3"   # originaux intacts
    assert len(cloner_famille((1, "I3"), index, 900, "C_", profondeur=2)[0]) == 6
