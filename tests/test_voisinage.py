from genealogie_acadienne.commun.voisinage import (
    cle, indexer, liens_de, proches_par_role, tous_les_liens, voisinage)


def test_liens_de(famille):
    pierre = famille[2]
    assert liens_de(pierre) == [("enfant_de", (1, "I1")), ("enfant_de", (1, "I2")),
                                ("parent_de", (1, "I6")), ("conjoint_de", (1, "I5"))]


def test_liens_symetriques(famille):
    liens = tous_les_liens(indexer(famille))
    assert ((1, "I1"), "parent_de", (1, "I3")) in liens
    assert ((1, "I3"), "enfant_de", (1, "I1")) in liens
    assert ((1, "I5"), "conjoint_de", (1, "I3")) in liens
    assert len(liens) == len(set(liens))


def test_voisinage_k(famille):
    index = indexer(famille)
    assert voisinage((1, "I6"), index, 0) == {(1, "I6"): 0}
    assert voisinage((1, "I6"), index, 1) == {(1, "I6"): 0, (1, "I3"): 1, (1, "I5"): 1}
    k2 = voisinage((1, "I6"), index, 2)
    assert k2[(1, "I1")] == 2 and k2[(1, "I2")] == 2 and (1, "I4") not in k2
    assert voisinage((1, "I99"), index, 2) == {}


def test_proche_absent_ignore(famille):
    index = indexer(famille[2:])  # sans Jean et Marie
    assert voisinage((1, "I3"), index, 1) == {(1, "I3"): 0, (1, "I5"): 1, (1, "I6"): 1}


def test_roles(famille):
    roles = proches_par_role(famille[2], indexer(famille))
    assert [cle(p) for p in roles["pere"]] == [(1, "I1")]
    assert [cle(p) for p in roles["mere"]] == [(1, "I2")]
    assert [cle(p) for p in roles["conjoints"]] == [(1, "I5")]
