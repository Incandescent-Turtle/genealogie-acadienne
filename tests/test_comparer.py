"""Comparaison de deux `Personne` construites à la main (aucune base)."""

from __future__ import annotations

import pandas as pd
import pytest

from genealogie_acadienne import comparer, criteres_concordants
from genealogie_acadienne.commun import comparaison as cp
from genealogie_acadienne.pipeline.apparier_personnes import comparer_groupe

from conftest import mariage, personne, proche


@pytest.mark.parametrize("annee_b, verdict, ecart", [
    (1700, "identique", 0),
    (1702, "proche", 2),
    (1710, "different", 10),
    (None, "inconnu", None),
])
def test_naissance(annee_b, verdict, ecart):
    a = personne(faits={"BIRT": 1700})
    b = personne(tree_id=2, faits={"BIRT": annee_b})
    r = cp.comparer_naissance(a, b)
    assert (r["metrique"], r["verdict"], r["ecart"]) == ("naissance", verdict, ecart)


def test_bapteme_utilise_chr_si_pas_de_bapm():
    a = personne(faits={"BAPM": 1700})
    b = personne(tree_id=2, faits={"CHR": 1701})
    assert cp.comparer_bapteme(a, b)["verdict"] == "proche"


@pytest.mark.parametrize("mariages_b, verdict", [
    ([mariage("Marie Léger", 1725)], "identique"),
    ([mariage("MARIE LEGER", 1727)], "proche"),
    ([mariage("Marie Leger", None)], "meme_conjoint"),
    ([mariage("Anne Comeau", 1725)], "autre_conjoint"),
    ([], "inconnu"),
])
def test_mariage(mariages_b, verdict):
    a = personne(mariages=[mariage("Marie Leger", 1725)])
    b = personne(tree_id=2, mariages=mariages_b)
    assert cp.comparer_mariage(a, b)["verdict"] == verdict


def test_mariage_conjoint_inconnu_compatible():
    a = personne(mariages=[mariage(None, 1725)])
    b = personne(tree_id=2, mariages=[mariage("Anne Comeau", 1726)])
    r = cp.comparer_mariage(a, b)
    assert (r["verdict"], r["n_proches"], r["n_exacts"]) == ("proche", 1, 0)


@pytest.mark.parametrize("parents_b, verdict, communs", [
    ([proche("Pierre BABIN")], "communs", ["pierre babin"]),
    ([proche("Paul Comeau")], "aucun_commun", []),
    ([], "inconnu", []),
])
def test_ascendants(parents_b, verdict, communs):
    a = personne(parents=[proche("Pierre Babin"), proche("Anne Leger")])
    b = personne(tree_id=2, parents=parents_b)
    r = cp.comparer_ascendants(a, b)
    assert (r["verdict"], r["communs"]) == (verdict, communs)


def test_periode_estimee_via_enfants():
    a = personne(faits={"BIRT": 1700, "DEAT": 1760})
    b = personne(tree_id=2, enfants=[proche("Paul Babin", 1730)])
    r = cp.comparer_periode_estimee(a, b)
    assert r["b"] == (1730 - cp.ECART_GENERATION, 1730)
    assert (r["methode_b"], r["ecart"], r["verdict"]) == ("via enfants", 0, "chevauchement")


def test_periode_estimee_inconnue():
    r = cp.comparer_periode_estimee(personne(), personne(tree_id=2))
    assert (r["a"], r["b"], r["verdict"]) == (None, None, "inconnu")


def _paire_concordante():
    commun = dict(
        faits={"BIRT": 1700, "DEAT": 1760},
        mariages=[mariage("Marie Leger", 1725)],
        parents=[proche("Pierre Babin", 1670)],
        enfants=[proche("Paul Babin", 1730)],
    )
    return personne(**commun), personne(tree_id=2, person_id="X7", **commun)


def test_comparer_rapport_complet():
    a, b = _paire_concordante()
    rapport = comparer(a, b)
    assert list(rapport) == ["naissance", "bapteme", "deces", "sepulture", "mariage",
                             "periode_estimee", "ascendants", "descendants"]
    assert criteres_concordants(rapport) == [
        "naissance", "deces", "mariage", "ascendants", "descendants"]


def test_comparer_rien_en_commun():
    a = personne(faits={"BIRT": 1700})
    b = personne(tree_id=2, faits={"BIRT": 1750})
    assert criteres_concordants(comparer(a, b)) == []


def test_comparer_groupe_ligne_de_base():
    """Méthode de base : même nom exact + nombre de critères concordants."""
    a, b = _paire_concordante()
    c = personne(tree_id=1, person_id="I3", faits={"BIRT": 1790})  # même arbre que `a`
    groupe = pd.DataFrame({"tree_id": [1, 2, 1], "person_id": ["I1", "X7", "I3"]})
    personnes = {(1, "I1"): a, (2, "X7"): b, (1, "I3"): c}

    lignes = comparer_groupe(groupe, personnes, min_criteres=1)

    # (I1, I3) : même arbre, sautée ; (I3, X7) : aucun critère, non retenue
    assert len(lignes) == 1
    assert lignes[0][:6] == (1, "I1", 2, "X7", 5,
                             "naissance, deces, mariage, ascendants, descendants")
