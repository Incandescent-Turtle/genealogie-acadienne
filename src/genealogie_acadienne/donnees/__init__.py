"""
Accès à la base WebTrees : connexion (`DBConfig`, `get_connection`) et
chargement des noms et des `Personne`. Dépend de `commun`, jamais de `pipeline`.
"""

from .db import DBConfig, get_connection, load_env_file, set_table_prefix
from .noms import ARBRES_IGNORES, charger_personnes, ids_arbres_ignores
from .personnes import charger_groupe, charger_personne

__all__ = [
    "DBConfig", "get_connection", "load_env_file", "set_table_prefix",
    "charger_personnes", "ids_arbres_ignores", "ARBRES_IGNORES",
    "charger_groupe", "charger_personne",
]
