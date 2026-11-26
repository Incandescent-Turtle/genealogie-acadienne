"""
Connexion partagée à la base de données WebTree (MariaDB).
Tous les scripts importent ce module pour s'y connecter.

Importer ce module n'ouvre AUCUNE connexion et ne lit pas le fichier `.env`.
Les paramètres de connexion viennent :
  - d'un `DBConfig` passé explicitement à `get_connection(config)`, ou
  - des variables d'environnement DB_HOST, DB_USER, DB_PASS, DB_NAME, DB_PORT.
`load_env_file()` charge un `.env` dans l'environnement (commodité optionnelle,
utilisée par les points d'entrée).
"""

from __future__ import annotations

import os
import sqlite3
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
import pymysql

if TYPE_CHECKING:
    from pymysql.connections import Connection

    # Connexion acceptée par les chargeurs : MariaDB, ou SQLite (`connexion_parquet`).
    type Connexion = Connection | sqlite3.Connection

PREFIXE_PAR_DEFAUT = "wt_"
# Préfixe forcé par `set_table_prefix` (sinon DB_PREFIX, sinon "wt_").
TABLE_PREFIX: str | None = None


@dataclass(frozen=True)
class DBConfig:
    """Paramètres de connexion à la base WebTrees."""
    host: str
    user: str
    password: str
    database: str
    port: int = 3306

    def __repr__(self) -> str:  # ne jamais afficher le mot de passe
        return (f"DBConfig(host={self.host!r}, user={self.user!r}, "
                f"database={self.database!r}, port={self.port!r})")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> DBConfig:
        """Construit la config depuis les variables d'environnement
        (DB_HOST, DB_USER, DB_PASS, DB_NAME, DB_PORT)."""
        env = os.environ if env is None else env
        host = env.get("DB_HOST")
        user = env.get("DB_USER")
        password = env.get("DB_PASS")
        name = env.get("DB_NAME")
        port = int(env.get("DB_PORT", 3306))

        if not all([host, user, password, name]):
            raise ValueError(
                "Alerte : Il manque un ou plusieurs identifiants "
                "(DB_HOST, DB_USER, DB_PASS, DB_NAME) dans l'environnement ou le fichier .env."
            )
        return cls(host=host, user=user, password=password, database=name, port=port)


def load_env_file(path: str | os.PathLike | None = None, override: bool = False) -> bool:
    """Charge un fichier `.env` dans `os.environ` (commodité optionnelle).

    Sans `path`, on cherche un `.env` depuis le dossier courant vers le haut.
    Renvoie True si un fichier a été chargé.
    """
    from dotenv import find_dotenv, load_dotenv

    if path is None:
        path = find_dotenv(usecwd=True)
        if not path:
            return False
    return load_dotenv(path, override=override)


def set_table_prefix(prefixe: str | None) -> None:
    """Force le préfixe des tables (None = revenir à DB_PREFIX / "wt_")."""
    global TABLE_PREFIX
    TABLE_PREFIX = prefixe


def t(nom_court):
    """Renvoie le nom complet d'une table avec le préfixe.

    Exemple : t("individuals") -> "wt_individuals"
    """
    prefixe = TABLE_PREFIX if TABLE_PREFIX is not None else os.getenv("DB_PREFIX", PREFIXE_PAR_DEFAUT)
    return f"{prefixe}{nom_court}"


def get_connection(config: DBConfig | None = None) -> Connection:
    """Ouvre une connexion. Sans `config`, on lit les variables d'environnement."""
    if config is None:
        config = DBConfig.from_env()

    return pymysql.connect(
        host=config.host,
        user=config.user,
        password=config.password,
        database=config.database,
        port=config.port,
        charset="utf8mb4",
    )


def run_query(sql, params=None, conn=None):
    """Exécute une requête SELECT et renvoie un DF de Pandas.

    `conn` est une connexion MariaDB (pymysql) ou SQLite (`connexion_parquet`) :
    les requêtes sont écrites avec des marques `%s`, changées en `?` pour SQLite.
    """
    if isinstance(conn, sqlite3.Connection):
        return pd.read_sql(sql.replace("%s", "?"), conn, params=tuple(params or ()))
    fermer = False
    # Si une connexion n'est pas fournie, on en ouvre une et on la ferme à la fin.
    if conn is None:
        conn = get_connection()
        fermer = True
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=".*pandas only supports SQLAlchemy connectable.*"
            )
            df = pd.read_sql(sql, conn, params=params)
    finally:
        if fermer:
            conn.close()
    return df


def execute(sql, params=None, conn=None, many=False):
    """Exécute une requête d'écriture (CREATE, INSERT, UPDATE...) et valide.

    Si `many=True`, `params` est une liste de tuples et on utilise `executemany`.
    Renvoie le nombre de lignes affectées.
    """
    fermer = False
    if conn is None:
        conn = get_connection()
        fermer = True
    try:
        with conn.cursor() as cur:
            if many:
                n = cur.executemany(sql, params or [])
            else:
                n = cur.execute(sql, params)
        conn.commit()
        return n
    finally:
        if fermer:
            conn.close()
