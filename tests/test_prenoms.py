"""Alias « dit » et appariement par prénoms partagés (module pur)."""

from __future__ import annotations

import pandas as pd
import pytest

from genealogie_acadienne import alias_dit, tokens_prenoms, trouver_paires


@pytest.mark.parametrize("nom, alias", [
    ("Jean Doucet dit Laverdure", ["laverdure"]),
    ("Marie Bourgeois dite Clarisse ou Rose", ["clarisse", "rose"]),
    ("Pierre Babin dit La Grange", ["la grange"]),
    ("Marie Ouellet", []),            # « ou » seul n'est pas un marqueur
    ("Jean dit", []),
    (None, []),
])
def test_alias_dit(nom, alias):
    assert alias_dit(nom) == alias


def test_tokens_prenoms():
    assert tokens_prenoms("Marie Bourgeois dite Rose", "bourgeois") == {"marie", "rose"}
    assert tokens_prenoms("Abraham d'Entremont", "d'Entremont") == {"abraham"}
    assert tokens_prenoms("Marie Clorisse BOURGEOIS dite Clarisse ou Rose", "Bourgeois") == {
        "marie", "clorisse", "clarisse", "rose"}


def _df(lignes):
    return pd.DataFrame(lignes, columns=["tree_id", "person_id", "nom_complet", "nom_famille"])


PERSONNES = _df([
    (1, "I1", "Marie Louise Comeaux", "Comeaux"),
    (2, "I2", "Louise Comeaux", "Comeaux"),
    (3, "I3", "Louise Comeaux", "Comeaux"),
    (3, "I4", "Louise Comeaux", "Comeaux"),       # même arbre que I3
    (2, "I5", "Marie Louise Geneviève Comeaux", "Comeaux"),
    (4, "I6", "Louise Babin", "Babin"),           # autre nom de famille
    (4, "I7", "Rose Comeaux", None),              # nom de famille inconnu : ignorée
])


def _paires(df, **kw):
    p = trouver_paires(df, **kw)
    return {(a, b, e) for a, b, e in zip(p["person_id_a"], p["person_id_b"], p["exact"])}


def test_exact():
    assert _paires(PERSONNES) == {("I2", "I3", True), ("I2", "I4", True)}


def test_partage2_garde_les_exactes_a_un_prenom():
    """Corrigé par rapport à la branche appariement-prenoms : deux « Louise Comeaux »
    restent appariées en partage2 même si elles n'ont qu'un prénom."""
    assert _paires(PERSONNES, type_appariement="partage2") == {
        ("I2", "I3", True), ("I2", "I4", True), ("I1", "I5", False)}


def test_partage1_prenom_principal_omis():
    paires = _paires(PERSONNES, type_appariement="partage1")
    assert ("I1", "I2", False) in paires        # Marie Louise ~ Louise
    assert ("I3", "I4", True) not in paires     # même arbre
    assert not any("I6" in (a, b) for a, b, _ in paires)
    tri = trouver_paires(PERSONNES, type_appariement="partage1")
    assert tri["exact"].tolist() == sorted(tri["exact"].tolist(), reverse=True)


def test_meme_arbre_et_type_inconnu():
    assert ("I3", "I4", True) in _paires(PERSONNES, entre_arbres=False)
    with pytest.raises(ValueError):
        trouver_paires(PERSONNES, type_appariement="flou")
    assert trouver_paires(PERSONNES.iloc[:0]).empty
