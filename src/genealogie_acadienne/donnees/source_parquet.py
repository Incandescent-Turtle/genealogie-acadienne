"""
Lire un export Parquet (`exporter_base`) avec les mêmes chargeurs que la base.

L'export Parquet est une copie hors ligne de la base WebTrees. Pour ne pas écrire
les chargements deux fois, `connexion_parquet` copie les tables utiles dans une
base SQLite en mémoire (bibliothèque standard, aucun serveur) : `charger_personnes`,
`charger_groupe` et `instantane_depuis_base` y exécutent leurs requêtes telles quelles.

    conn = connexion_parquet("data/parquet")          # ou get_connection() (MariaDB)
    personnes = charger_groupe(conn, [(1, "I1")])
    instantane_depuis_base(conn, "chemin/instantane")

`with ouvrir_connexion(parquet) as conn:` choisit l'export si on donne un dossier,
sinon MariaDB (`.env`), et ferme la connexion. Les scripts de `pipeline` l'exposent
avec l'option `--parquet DOSSIER`.

Différences avec MariaDB : SQLite compare le texte en tenant compte de la casse
(MariaDB l'ignore en général), ce qui ne change rien pour les codes WebTrees
(`NAME`, `FAMC`...) ni pour les identifiants. `REGEXP` est fourni par Python (`re`).
La copie est en mémoire : rien n'est écrit dans l'export.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from .db import get_connection, load_env_file, t
from .export_parquet import lire_table

if TYPE_CHECKING:
    from .db import Connexion

# Tables (sans préfixe) copiées par défaut : celles lues par les chargeurs
# (`noms`, `personnes`) et par les scripts de `pipeline`. Copiées en entier.
TABLES_PAR_DEFAUT = ("gedcom", "individuals", "name", "families", "link", "dates", "places")

# Index sur les colonnes des filtres et jointures.
INDEX: dict[str, tuple[tuple[str, ...], ...]] = {
    "individuals": (("i_file", "i_id"),),
    "name": (("n_file", "n_id"),),
    "families": (("f_file", "f_id"), ("f_file", "f_husb"), ("f_file", "f_wife")),
    "link": (("l_file", "l_from"), ("l_file", "l_to")),
    "dates": (("d_file", "d_gid"), ("d_fact",)),
}


def _regexp(motif: str, valeur: object) -> bool:
    """`valeur REGEXP motif` de MariaDB (SQLite n'a pas de REGEXP par défaut)."""
    return valeur is not None and re.search(motif, str(valeur)) is not None


def connexion_parquet(
    dossier: str | Path, tables: Sequence[str] = TABLES_PAR_DEFAUT
) -> sqlite3.Connection:
    """Base SQLite en mémoire avec les `tables` (noms sans préfixe, voir `t`) de
    l'export `dossier`, toutes colonnes comprises. À fermer avec `.close()`."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.create_function("REGEXP", 2, _regexp, deterministic=True)
        for nom in tables:
            table = t(nom)
            lire_table(dossier, table).to_sql(table, conn, index=False)
            for i, cols in enumerate(INDEX.get(nom, ())):
                conn.execute(f'CREATE INDEX "{table}_ix{i}" ON "{table}" ({", ".join(cols)})')
        conn.commit()
    except BaseException:
        conn.close()
        raise
    return conn


@contextmanager
def ouvrir_connexion(parquet: str | Path | None = None) -> Iterator[Connexion]:
    """Connexion fermée à la sortie du `with` : l'export Parquet `parquet` (copie en
    mémoire), ou sans `parquet` la base MariaDB des variables d'environnement / `.env`.

        with ouvrir_connexion(args.parquet) as conn:
            personnes = charger_groupe(conn, gens)
    """
    if parquet is not None:
        conn: Connexion = connexion_parquet(parquet)
    else:
        load_env_file(override=True)
        conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def ajouter_option_parquet(parser: argparse.ArgumentParser) -> None:
    """Ajoute `--parquet DOSSIER` à un script (sans l'option : MariaDB, `.env`)."""
    parser.add_argument(
        "--parquet", metavar="DOSSIER",
        help="lire l'export Parquet DOSSIER au lieu de la base MariaDB (.env)")
