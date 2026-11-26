"""Export Parquet lu avec les mêmes chargeurs que la base (mini-base, aucune vraie base)."""

from __future__ import annotations

import json

import fausse_base
import pandas as pd
import pytest

from genealogie_acadienne.donnees import (
    charger_groupe,
    charger_personnes,
    connexion_parquet,
    instantane_depuis_base,
    lire_instantane,
)

IDS = [(1, x[0]) for x in fausse_base.INDIVIDUS]


@pytest.fixture
def export(tmp_path):
    """La mini-base écrite comme un export Parquet."""
    base = fausse_base.creer()
    fausse_base.exporter(base, tmp_path / "export")
    base.close()
    return tmp_path / "export"


def test_memes_personnes_que_la_base(export):
    base = fausse_base.creer()
    conn = connexion_parquet(export)
    try:
        assert charger_groupe(conn, IDS) == charger_groupe(base, IDS)
        pd.testing.assert_frame_equal(charger_personnes(conn), charger_personnes(base))
    finally:
        conn.close()
        base.close()


def test_table_manquante(export):
    (export / "wt_link.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="wt_link"):
        connexion_parquet(export)


def test_instantane_depuis_export(export, tmp_path):
    conn = connexion_parquet(export)
    try:
        dossier = instantane_depuis_base(conn, tmp_path / "snap", source="export", sha256="abc")
    finally:
        conn.close()
    base = fausse_base.creer()
    try:
        attendu = charger_groupe(base, IDS)
    finally:
        base.close()
    cle = lambda p: (p.tree_id, p.person_id)
    assert sorted(lire_instantane(dossier), key=cle) == sorted(attendu.values(), key=cle)
    manifeste = json.loads((dossier / "manifeste.json").read_text(encoding="utf-8"))
    assert manifeste["source"] == "export" and manifeste["sha256"] == "abc"
