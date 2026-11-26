"""
Accès à la base WebTrees : connexion (`DBConfig`, `get_connection`) et
chargement des noms et des `Personne`, instantanés Parquet,
export des tables brutes en Parquet (`exporter_base`, `lire_table`). Dépend de `commun`, jamais de `pipeline`.
"""

from .db import DBConfig, get_connection, load_env_file, set_table_prefix
from .noms import ARBRES_IGNORES, charger_personnes, ids_arbres_ignores
from .instantane import ecrire_instantane, instantane_depuis_base, lire_instantane, lire_manifeste
from .personnes import charger_groupe, charger_personne
from .export_parquet import exporter_base, lire_table

__all__ = [
    "DBConfig", "get_connection", "load_env_file", "set_table_prefix",
    "charger_personnes", "ids_arbres_ignores", "ARBRES_IGNORES",
    "charger_groupe", "charger_personne",
    "ecrire_instantane", "lire_instantane", "lire_manifeste", "instantane_depuis_base",
    "exporter_base", "lire_table",
]
