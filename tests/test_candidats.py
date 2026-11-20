from familles import personne

from genealogie_acadienne.commun.candidats import IndexCandidats, cles_blocage, generer_candidats


def test_cles_blocage_noms_alternatifs():
    p = personne("I1", "Marie Louise Comeaux", "F", nom_famille="Comeaux",
                 noms_alternatifs=["Marie Babin"])
    assert {nf for nf, _ in cles_blocage(p)} == {"como", "babin"}


def test_candidats_relaches():
    requete = personne("Q", "Marie Louise Comeaux", "F", tree_id=9, nom_famille="Comeaux")
    population = [
        personne("A", "Louise Comeau", "F", tree_id=1, nom_famille="Comeau"),     # prénom omis + variante
        personne("B", "Mary Comeaux", "F", tree_id=2, nom_famille="Comeaux"),      # anglicisé
        personne("C", "Rose Comeau dite Louise", "F", tree_id=3, nom_famille="Comeau"),  # alias
        personne("D", "Anne Comeau", "F", tree_id=1, nom_famille="Comeau"),        # aucun prénom commun
        personne("E", "Louis Comeau", "M", tree_id=1, nom_famille="Comeau"),       # autre prénom
        personne("F", "Louise Cormier", "F", tree_id=1, nom_famille="Cormier"),    # autre nom
        personne("G", "Marie Comeau", "F", tree_id=9, nom_famille="Comeau"),       # même arbre
        personne("H", "Marie Comeau", "M", tree_id=4, nom_famille="Comeau"),       # sexe différent
        personne("J", "Marie Comeau", "U", tree_id=5, nom_famille="Comeau"),       # sexe inconnu : gardée
    ]
    attendus = [(1, "A"), (2, "B"), (3, "C"), (5, "J")]
    index = IndexCandidats(population + [requete])
    assert index.candidats(requete) == attendus
    assert (9, "G") in index.candidats(requete, exclure_meme_arbre=False)
    assert (4, "H") in index.candidats(requete, sexe_compatible=False)
    assert index.candidats(requete, arbres_exclus=[1, 2]) == [(3, "C"), (5, "J")]
    assert generer_candidats([requete], population)[(9, "Q")] == attendus
