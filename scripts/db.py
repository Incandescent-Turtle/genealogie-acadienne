"""
Connexion partagée à la base de données WebTree (MariaDB).
Tous les scripts importent ce module pour s'y connecter.
"""

import os

import pandas as pd
import pymysql
from dotenv import load_dotenv
import warnings

warnings.filterwarnings(
    "ignore", 
    message=".*pandas only supports SQLAlchemy connectable.*"
)

load_dotenv(override=True)
TABLE_PREFIX = os.getenv("DB_PREFIX", "wt_")

def t(nom_court):
    """Renvoie le nom complet d'une table avec le préfixe.

    Exemple : t("individuals") -> "wt_individuals"
    """
    return f"{TABLE_PREFIX}{nom_court}"


def get_connection():
    load_dotenv(override=True)

    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    name = os.getenv("DB_NAME")
    port = int(os.getenv("DB_PORT", 3306))

    if not all([host, user, password, name]):
        raise ValueError(
            "Alerte : Il manque un ou plusieurs identifiants dans ton fichier .env."
        )

    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=name,
        port=port,
        charset="utf8mb4",
    )


def run_query(sql, params=None, conn=None):
    """Exécute une requête SELECT et renvoie un DF de Pandas."""
    fermer = False
    # Si une connexion n'est pas fournie, on en ouvre une et on la ferme à la fin.
    if conn is None:
        conn = get_connection()
        fermer = True
    try:
        df = pd.read_sql(sql, conn, params=params)
    finally:
        if fermer:
            conn.close()
    return df
