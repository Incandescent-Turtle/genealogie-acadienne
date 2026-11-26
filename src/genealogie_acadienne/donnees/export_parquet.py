"""
Exporter les tables d'une base MariaDB/MySQL en Parquet, une table par fichier.

Le résultat est un dossier :
  <table>.parquet   une copie fidèle de la table (types tirés du schéma SQL)
  manifeste.json    source, date, version du paquet, lignes et colonnes par table

Par défaut, on n'exporte PAS les tables d'utilisateurs, de sessions, de journaux
ni de configuration de WebTrees (`TABLES_EXCLUES`), quel que soit le préfixe.
Les tables généalogiques (`TABLES_GENEALOGIQUES`) et les tables inconnues de
WebTrees (ex. `person_comparisons`) sont exportées. `tables=` / `exclure=`
permettent de choisir autrement.

Les dates et heures (`timestamp`, `datetime`) sont lues en UTC.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.parquet as pq
import pymysql.cursors

from .instantane import _version_paquet

if TYPE_CHECKING:
    from pymysql.connections import Connection

FICHIER_MANIFESTE = "manifeste.json"
LIGNES_PAR_LOT = 20_000

# Noms de tables WebTrees sans le préfixe (`wt_`, `usa_`...).
TABLES_GENEALOGIQUES = frozenset({
    "gedcom", "individuals", "families", "sources", "other", "media", "media_file",
    "link", "name", "dates", "places", "placelinks", "place_location",
})
TABLES_EXCLUES = frozenset({
    # utilisateurs, sessions, activité
    "user", "user_setting", "user_gedcom_setting", "session", "message", "log",
    "hit_counter", "change", "news", "favorite", "password_reset",
    # configuration du site et des arbres, tampon d'import
    "site_setting", "gedcom_setting", "default_gedcom_setting", "default_resn",
    "block", "block_setting", "module", "module_setting", "module_privacy",
    "gedcom_chunk",
})

_ENTIERS = {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "year"}
_TEXTES = {"char", "varchar", "tinytext", "text", "mediumtext", "longtext", "enum", "set", "json"}
_BINAIRES = {"binary", "varbinary", "tinyblob", "blob", "mediumblob", "longblob", "bit"}


def _termine_par(table: str, noms: Iterable[str]) -> bool:
    """`wt_user` se termine par `user` (préfixe quelconque, séparé par `_`)."""
    return any(table == n or table.endswith(f"_{n}") for n in noms)


def est_exclue(table: str) -> bool:
    """Table WebTrees d'utilisateurs, d'activité ou de configuration."""
    return _termine_par(table, TABLES_EXCLUES)


def choisir_tables(
    disponibles: Iterable[str],
    tables: Sequence[str] | None = None,
    exclure: Sequence[str] = (),
) -> list[str]:
    """Tables à exporter, triées. `tables` remplace le choix par défaut."""
    disponibles = sorted(disponibles)
    if tables is not None:
        inconnues = sorted(set(tables) - set(disponibles))
        if inconnues:
            raise ValueError(f"Tables absentes de la base : {', '.join(inconnues)}")
        choix = sorted(set(tables))
    else:
        choix = [t for t in disponibles if not est_exclue(t)]
    return [t for t in choix if t not in set(exclure)]


def type_arrow(type_sql: str, type_colonne: str, precision: int | None, echelle: int | None) -> pa.DataType:
    """Type Arrow d'une colonne, d'après `information_schema.COLUMNS`
    (`DATA_TYPE`, `COLUMN_TYPE`, `NUMERIC_PRECISION`, `NUMERIC_SCALE`)."""
    t = type_sql.lower()
    if t in _ENTIERS:
        return pa.uint64() if t == "bigint" and "unsigned" in type_colonne.lower() else pa.int64()
    if t in {"float", "double", "real"}:
        return pa.float64()
    if t == "decimal":
        return pa.decimal128(precision or 10, echelle or 0)
    if t in _TEXTES:
        return pa.string()
    if t in _BINAIRES:
        return pa.binary()
    if t == "date":
        return pa.date32()
    if t in {"datetime", "timestamp"}:
        return pa.timestamp("us", tz="UTC")
    if t == "time":
        return pa.duration("us")
    raise ValueError(f"Type SQL non pris en charge : {type_colonne}")


def _requete(conn: Connection, sql: str, params: Any = None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def schema_table(conn: Connection, table: str) -> tuple[pa.Schema, list[dict[str, str]]]:
    """Schéma Arrow d'une table et description de ses colonnes SQL."""
    lignes = _requete(conn, """
        SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION""", (table,))
    champs, colonnes = [], []
    for nom, type_sql, type_colonne, precision, echelle in lignes:
        try:
            champs.append(pa.field(nom, type_arrow(type_sql, type_colonne, precision, echelle)))
        except ValueError as e:
            raise ValueError(f"{table}.{nom} : {e}") from None
        colonnes.append({"nom": nom, "type_sql": type_colonne})
    return pa.schema(champs), colonnes


def exporter_table(conn: Connection, table: str, chemin: Path) -> tuple[int, list[dict[str, str]]]:
    """Écrit `table` dans `chemin` par lots. Renvoie (lignes, colonnes)."""
    schema, colonnes = schema_table(conn, table)
    n = 0
    with (pq.ParquetWriter(chemin, schema, compression="zstd") as ecrivain,
          conn.cursor(pymysql.cursors.SSCursor) as cur):  # lecture en flux
        cur.execute(f"SELECT * FROM `{table}`")
        while lot := cur.fetchmany(LIGNES_PAR_LOT):
            colonnes_lot = list(zip(*lot))
            try:
                tableau = pa.table(
                    [pa.array(v, type=c.type) for v, c in zip(colonnes_lot, schema)], schema=schema)
            except (pa.ArrowInvalid, pa.ArrowTypeError) as e:
                raise ValueError(f"{table} : valeur non convertible ({e})") from None
            ecrivain.write_table(tableau)
            n += len(lot)
    return n, colonnes


def exporter_base(
    conn: Connection,
    dossier: str | Path,
    tables: Sequence[str] | None = None,
    exclure: Sequence[str] = (),
    source: dict[str, Any] | None = None,
    ecraser: bool = False,
) -> dict[str, Any]:
    """Exporte les tables choisies de la base de `conn` dans `dossier`. Renvoie le manifeste.

    `source` est ajouté tel quel au manifeste (ex. fichier dump et sa somme SHA-256).
    Refuse un dossier qui contient déjà un export, sauf `ecraser=True`.
    """
    dossier = Path(dossier)
    if (dossier / FICHIER_MANIFESTE).exists():
        if not ecraser:
            raise FileExistsError(f"{dossier} contient déjà un export (utiliser ecraser=True).")
        for ancien in dossier.glob("*.parquet"):
            ancien.unlink()
        (dossier / FICHIER_MANIFESTE).unlink()
    dossier.mkdir(parents=True, exist_ok=True)

    with conn.cursor() as cur:
        cur.execute("SET time_zone = '+00:00'")
    disponibles = [r[0] for r in _requete(conn, """
        SELECT TABLE_NAME FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'""")]
    choix = choisir_tables(disponibles, tables, exclure)

    resume: dict[str, Any] = {}
    for table in choix:
        print(f"  {table}...", end=" ", flush=True, file=sys.stderr)
        n, colonnes = exporter_table(conn, table, dossier / f"{table}.parquet")
        print(f"{n} lignes", file=sys.stderr)
        resume[table] = {"lignes": n, "colonnes": colonnes}

    manifeste = {
        "cree_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "version_paquet": _version_paquet(),
        "source": source or {},
        "tables": resume,
        "tables_non_exportees": sorted(set(disponibles) - set(choix)),
    }
    (dossier / FICHIER_MANIFESTE).write_text(json.dumps(manifeste, indent=2, ensure_ascii=False) + "\n")
    return manifeste

