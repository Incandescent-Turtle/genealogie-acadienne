"""Formes canoniques des noms (aucune base)."""

import pytest

from genealogie_acadienne.commun.variantes import (
    cle_nom_famille, cle_prenom, cles_noms_famille, cles_prenoms, nom_famille_probable)


@pytest.mark.parametrize("a, b", [
    ("Comeau", "Comeaux"), ("Thibodeau", "Thibodeaux"), ("Arsenault", "Arseneau"),
    ("Doucet", "Doucette"), ("Melanson", "Melançon"), ("Theriot", "Terriot"),
    ("Thériault", "Theriot"), ("Savoie", "Savoy"), ("Boudreau", "Boudrot"),
    ("LeBlanc", "Le Blanc"), ("Landry", "Landrie"), ("d'Entremont", "Entremont"),
])
def test_variantes_nom_famille(a, b):
    assert cle_nom_famille(a) == cle_nom_famille(b)


def test_noms_differents_restent_differents():
    assert cle_nom_famille("Comeau") != cle_nom_famille("Cormier")
    assert cle_nom_famille("Babin") != cle_nom_famille("Bourg")


def test_prenoms():
    assert cle_prenom("Mary") == cle_prenom("Marie") == "marie"
    assert cle_prenom("John") == "jean" and cle_prenom("Élisabeth") == "elisabeth"
    assert cle_prenom("Osite") == "osite"  # absent de la table : tel quel
    assert cles_prenoms("Mary Louise Comeaux dite Rose", "Comeaux") == {"marie", "louise", "rosalie"}


def test_dit_comme_nom_de_famille():
    assert cles_noms_famille("Doucet", "Jean Doucet dit Laverdure") == {
        cle_nom_famille("Doucet"), cle_nom_famille("Laverdure")}
    assert cles_noms_famille("", None) == frozenset()


def test_nom_famille_probable():
    assert nom_famille_probable("Jean Doucet dit Laverdure", "") == "doucet"
    assert nom_famille_probable("Jean", "") == ""
    assert nom_famille_probable("x", "Babin") == "Babin"
