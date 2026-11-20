"""Correspondance exacte des noms (après normalisation), sans base."""

from __future__ import annotations

import pandas as pd

from genealogie_acadienne import chercher_meme_nom, normaliser, trouver_noms_partages
from genealogie_acadienne.donnees import noms as donnees_noms


def test_normaliser():
    assert normaliser("  Marie-Josèphe  LÉGER ") == "marie josephe leger"
    assert normaliser("Jean /Babin/") == "jean babin"
    assert normaliser(None) == ""


def _df(lignes):
    df = pd.DataFrame(lignes, columns=["tree_id", "person_id", "nom_complet"])
    df["nom_norm"] = df["nom_complet"].map(normaliser)
    return df


def test_trouver_noms_partages():
    df = _df([
        (1, "I1", "Jean Babin"),
        (2, "I9", "JEAN BABIN"),      # même nom, autre arbre
        (3, "I4", "Jéan Bábin"),      # accents ignorés
        (1, "I2", "Marie Leger"),
        (1, "I3", "Marie Léger"),     # même nom, MÊME arbre seulement
        (2, "I5", "Pierre Comeau"),
        (3, "I6", "Pierre Comeau"),
        (2, "I7", ""),                # nom vide : ignoré
        (3, "I8", ""),
    ])

    partages = trouver_noms_partages(df)

    assert set(partages["nom_norm"]) == {"jean babin", "pierre comeau"}
    babin = partages[partages["nom_norm"] == "jean babin"]
    assert len(babin) == 3 and set(babin["n_arbres"]) == {3}
    # le groupe le plus gros reçoit le groupe_id 1
    assert set(babin["groupe_id"]) == {1}
    assert set(partages[partages["nom_norm"] == "pierre comeau"]["groupe_id"]) == {2}


def test_chercher_meme_nom():
    df = _df([(1, "I1", "Jean Babin"), (2, "I2", "Jean Babin"), (1, "I3", "Paul Babin")])
    trouves = chercher_meme_nom(df, "JEAN  babin", tree_id=1)
    assert trouves["person_id"].tolist() == ["I1"]


def test_charger_personnes_avec_fausse_base(monkeypatch):
    """`charger_personnes` avec une fausse couche SQL : arbres ignorés + normalisation."""
    def faux_run_query(sql, params=None, conn=None):
        if "gedcom" in sql:
            return pd.DataFrame({"gedcom_id": [1, 2], "gedcom_name": ["Babin_Test", "BON"]})
        return pd.DataFrame({
            "tree_id": [1, 2, 2],
            "person_id": ["I1", "I2", "I2"],   # doublon (tree_id, person_id)
            "nom_complet": ["Jean Babin", "Élise Comeau", "Élise Comeau"],
            "nom_famille": ["Babin", "@N.M.", "@N.M."],
        })

    monkeypatch.setattr(donnees_noms, "run_query", faux_run_query)

    df = donnees_noms.charger_personnes(conn=object())

    assert df[["tree_id", "person_id", "nom_norm"]].values.tolist() == [[2, "I2", "elise comeau"]]
    assert df["nom_famille"].isna().all()  # « @N.M. » = inconnu
