"""Export Parquet des tables brutes : choix des tables, types, fichiers écrits.

Aucune vraie base : une fausse connexion répond aux deux requêtes
`information_schema` et au `SELECT *`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from genealogie_acadienne.donnees.export_parquet import (
    FICHIER_MANIFESTE,
    choisir_tables,
    est_exclue,
    exporter_base,
    lire_table,
    type_arrow,
)
from genealogie_acadienne.donnees.mariadb_local import version_portable

# table -> (colonnes (nom, DATA_TYPE, COLUMN_TYPE, précision, échelle), lignes)
BASE = {
    "wt_individuals": (
        [("i_id", "varchar", "varchar(20)", None, None), ("i_file", "int", "int(11)", 10, 0),
         ("i_sex", "enum", "enum('U','M','F')", None, None),
         ("i_gedcom", "longtext", "longtext", None, None)],
        [("I1", 1, "M", "0 @I1@ INDI\n1 NAME Jean /Babin/"),
         ("I2", 1, "F", "0 @I2@ INDI\n1 NAME Marie /Léger/ \\ 'dite' Rose"),
         ("I3", 2, "U", None)],
    ),
    "wt_place_location": (
        [("id", "int", "int(11)", 10, 0), ("latitude", "double", "double", 22, None),
         ("prix", "decimal", "decimal(8,2)", 8, 2), ("photo", "blob", "blob", None, None)],
        [(1, 45.5, Decimal("12.34"), b"\x00\xff"), (2, None, None, None)],
    ),
    "person_comparisons": (
        [("id", "int", "int(11)", 10, 0), ("comparison_date", "timestamp", "timestamp", None, None)],
        [(1, datetime(2026, 1, 2, 3, 4, 5))],
    ),
    "wt_user": ([("user_id", "int", "int(11)", 10, 0)], [(1,)]),
    "wt_session": ([("session_id", "varchar", "varchar(32)", None, None)], [("abc",)]),
}


class FauxCurseur:
    def __init__(self):
        self.lignes: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        if "information_schema.TABLES" in sql:
            self.lignes = [(t,) for t in BASE]
        elif "information_schema.COLUMNS" in sql:
            self.lignes = list(BASE[params[0]][0])
        elif sql.startswith("SELECT * FROM"):
            self.lignes = list(BASE[sql.split("`")[1]][1])
        else:
            self.lignes = []  # SET time_zone

    def fetchall(self):
        return self.lignes

    def fetchmany(self, n):
        lot, self.lignes = self.lignes[:n], self.lignes[n:]
        return lot


class FausseConnexion:
    def cursor(self, *args):
        return FauxCurseur()


def connexion() -> Any:
    return cast(Any, FausseConnexion())


def test_tables_exclues_quel_que_soit_le_prefixe():
    for t in ("wt_user", "wt_user_setting", "wt_session", "wt_message", "wt_log",
              "usa_default_gedcom_setting", "pfx_site_setting", "wt_gedcom_chunk"):
        assert est_exclue(t), t
    for t in ("wt_individuals", "wt_gedcom", "wt_name", "wt_dates", "wt_media_file",
              "person_comparisons", "person_comparisons0"):
        assert not est_exclue(t), t


def test_choisir_tables():
    dispo = ["wt_user", "wt_individuals", "wt_families", "person_comparisons"]
    assert choisir_tables(dispo) == ["person_comparisons", "wt_families", "wt_individuals"]
    assert choisir_tables(dispo, exclure=["person_comparisons"]) == ["wt_families", "wt_individuals"]
    assert choisir_tables(dispo, tables=["wt_user"]) == ["wt_user"]  # choix explicite
    with pytest.raises(ValueError, match="wt_absente"):
        choisir_tables(dispo, tables=["wt_absente"])


@pytest.mark.parametrize("args, attendu", [
    (("int", "int(11)", 10, 0), pa.int64()),
    (("bigint", "bigint(20) unsigned", 20, 0), pa.uint64()),
    (("tinyint", "tinyint(1)", 3, 0), pa.int64()),
    (("double", "double", 22, None), pa.float64()),
    (("decimal", "decimal(8,2)", 8, 2), pa.decimal128(8, 2)),
    (("enum", "enum('U','M','F')", None, None), pa.string()),
    (("longtext", "longtext", None, None), pa.string()),
    (("longblob", "longblob", None, None), pa.binary()),
    (("date", "date", None, None), pa.date32()),
    (("timestamp", "timestamp", None, None), pa.timestamp("us", tz="UTC")),
])
def test_type_arrow(args, attendu):
    assert type_arrow(*args) == attendu


def test_type_inconnu_refuse():
    with pytest.raises(ValueError, match="geometry"):
        type_arrow("geometry", "geometry", None, None)


def test_exporter_base(tmp_path, monkeypatch):
    monkeypatch.setattr("genealogie_acadienne.donnees.export_parquet.LIGNES_PAR_LOT", 2)  # plusieurs lots
    manifeste = exporter_base(connexion(), tmp_path, source={"fichier": "test.sql"})

    fichiers = sorted(p.name for p in tmp_path.iterdir())
    assert fichiers == [FICHIER_MANIFESTE, "person_comparisons.parquet",
                        "wt_individuals.parquet", "wt_place_location.parquet"]
    assert manifeste["tables_non_exportees"] == ["wt_session", "wt_user"]
    assert manifeste["tables"]["wt_individuals"]["lignes"] == 3
    assert json.loads((tmp_path / FICHIER_MANIFESTE).read_text())["source"] == {"fichier": "test.sql"}

    individus = pq.read_table(tmp_path / "wt_individuals.parquet")
    assert individus.column("i_file").type == pa.int64()
    assert individus.to_pylist()[1]["i_gedcom"] == "0 @I2@ INDI\n1 NAME Marie /Léger/ \\ 'dite' Rose"
    assert individus.to_pylist()[2]["i_gedcom"] is None

    lieux = pq.read_table(tmp_path / "wt_place_location.parquet").to_pylist()
    assert lieux[0] == {"id": 1, "latitude": 45.5, "prix": Decimal("12.34"), "photo": b"\x00\xff"}
    assert lieux[1] == {"id": 2, "latitude": None, "prix": None, "photo": None}

    date = pq.read_table(tmp_path / "person_comparisons.parquet").to_pylist()[0]["comparison_date"]
    assert date == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_export_existant_protege(tmp_path):
    exporter_base(connexion(), tmp_path)
    with pytest.raises(FileExistsError):
        exporter_base(connexion(), tmp_path)
    manifeste = exporter_base(connexion(), tmp_path, tables=["wt_user"], ecraser=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == [FICHIER_MANIFESTE, "wt_user.parquet"]
    assert list(manifeste["tables"]) == ["wt_user"]


def test_versions_portables():
    linux, windows = version_portable("Linux", "x86_64"), version_portable("Windows", "AMD64")
    assert linux is not None and windows is not None
    assert all(u.endswith(".tar.gz") for u in linux[0]) and len(linux[1]) == 64
    assert len(linux[0]) >= 2  # au moins un serveur de secours
    assert all(u.endswith(".zip") for u in windows[0])
    assert version_portable("Darwin", "arm64") is None


def test_lire_table_garde_les_entiers(tmp_path):
    exporter_base(connexion(), tmp_path)
    lieux = lire_table(tmp_path, "wt_place_location")
    assert str(lieux["id"].dtype) == "Int64"
    assert str(lieux["latitude"].dtype) == "Float64"
    assert lieux["latitude"].isna().tolist() == [False, True]

    # entier avec une valeur vide : reste Int64 (pd.read_parquet seul donnerait float64)
    pq.write_table(pa.table({"parent_id": pa.array([1, None, 3], pa.int64())}), tmp_path / "t.parquet")
    parents = lire_table(tmp_path, "t")
    assert str(parents["parent_id"].dtype) == "Int64"
    assert parents["parent_id"].isna().tolist() == [False, True, False]
    assert parents["parent_id"].dropna().astype(str).tolist() == ["1", "3"]  # pas "1.0"

    assert lire_table(tmp_path, "wt_individuals", colonnes=["i_id"]).columns.tolist() == ["i_id"]
    with pytest.raises(FileNotFoundError, match="wt_absente"):
        lire_table(tmp_path, "wt_absente")
