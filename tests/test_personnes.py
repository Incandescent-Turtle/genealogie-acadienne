"""Chargement des `Personne` sur une mini-base SQLite (aucune vraie base)."""

from __future__ import annotations

import pytest

import fausse_base
from genealogie_acadienne.donnees import personnes as donnees_personnes


@pytest.fixture
def gens(monkeypatch):
    """Toutes les personnes de la mini-base, chargées avec `charger_groupe`."""
    monkeypatch.setattr(donnees_personnes, "run_query", fausse_base.faux_run_query)
    conn = fausse_base.creer()
    ids = [(1, x[0]) for x in fausse_base.INDIVIDUS]
    return donnees_personnes.charger_groupe(conn, ids)


def test_proches_ont_leur_identifiant(gens):
    pierre = gens[(1, "I3")]
    assert pierre.nom_complet == "Pierre Babin" and pierre.faits == {"BIRT": 1726}
    assert sorted(p["person_id"] for p in pierre.parents) == ["I1", "I2"]
    assert [e["person_id"] for e in pierre.enfants] == ["I6"]
    assert [c["person_id"] for c in pierre.conjoints] == ["I5"]
    assert {p["person_id"]: p["naissance"] for p in pierre.parents} == {"I1": 1700, "I2": 1705}


def test_mariages_ont_l_identifiant_du_conjoint(gens):
    assert gens[(1, "I1")].mariages == [{
        "annee": 1725, "conjoint": "Marie Léger", "conjoint_norm": "marie leger",
        "conjoint_id": "I2",
    }]
    # F3 n'a qu'un parent : conjoint inconnu
    assert gens[(1, "I7")].mariages == [{
        "annee": None, "conjoint": None, "conjoint_norm": None, "conjoint_id": None,
    }]


def test_charger_personne_introuvable(monkeypatch):
    monkeypatch.setattr(donnees_personnes, "run_query", fausse_base.faux_run_query)
    with pytest.raises(ValueError):
        donnees_personnes.charger_personne(fausse_base.creer(), 1, "I99")
