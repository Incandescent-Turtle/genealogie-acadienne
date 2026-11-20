from collections import Counter

from genealogie_acadienne.commun.synthetique import generer_population
from genealogie_acadienne.commun.voisinage import indexer, tous_les_liens

PARAMS = dict(n_fondateurs=6, n_generations=4, n_arbres=4)


def test_deterministe():
    a, b = generer_population(graine=7, **PARAMS), generer_population(graine=7, **PARAMS)
    assert a.personnes == b.personnes and a.identites == b.identites
    assert generer_population(graine=8, **PARAMS).personnes != a.personnes


def test_structure():
    pop = generer_population(graine=1, **PARAMS)
    index = indexer(pop.personnes)
    assert len(index) == len(pop.personnes) == len(pop.identites)
    assert {p.tree_id for p in pop.personnes} == {1, 2, 3, 4}
    for p in pop.personnes:   # tous les liens pointent vers une personne du même arbre
        for proche in p.parents + p.enfants + p.conjoints:
            assert (p.tree_id, proche["person_id"]) in index
        assert len(p.parents) <= 2
    assert tous_les_liens(index)


def test_doublons_entre_arbres_et_bruit():
    pop = generer_population(graine=1, **PARAMS)
    assert any(n >= 2 for n in Counter(pop.identites.values()).values())  # recouvrements
    noms = [p.nom_complet for p in pop.personnes]
    assert any(" dit " in n or " dite " in n for n in noms)
    assert any(not p.faits.get("BIRT") for p in pop.personnes)            # champs manquants
    assert any(p.lieux for p in pop.personnes)
    assert all(p.sexe in "MF" for p in pop.personnes)
