"""Une mini-base WebTrees en mémoire (SQLite) pour tester les chargements.

Les requêtes du paquet sont écrites pour MySQL/MariaDB avec des marques `%s`.
SQLite comprend la même syntaxe pour ce qu'on utilise (backticks, NULLIF,
CASE, TRIM/REPLACE, sous-requêtes) : on remplace seulement `%s` par `?`.
Aucune vraie base, aucun réseau.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

# Arbre 1 :
#   F1 = I1 Jean Babin (1700) + I2 Marie Léger (1705), mariés en 1725
#        enfants : I3 Pierre Babin (1726), I4 Anne Babin (sans date)
#   F2 = I3 Pierre Babin + I5 Anne Comeau, mariés en 1750, enfant I6
#   F3 = I7 (sans conjoint) : famille avec un seul parent
SCHEMA = """
CREATE TABLE wt_gedcom (gedcom_id INTEGER, gedcom_name TEXT);
CREATE TABLE wt_individuals (i_id TEXT, i_file INTEGER, i_sex TEXT, i_gedcom TEXT);
CREATE TABLE wt_name (n_file INTEGER, n_id TEXT, n_num INTEGER, n_type TEXT,
                      n_full TEXT, n_givn TEXT, n_surn TEXT);
CREATE TABLE wt_families (f_id TEXT, f_file INTEGER, f_husb TEXT, f_wife TEXT);
CREATE TABLE wt_link (l_file INTEGER, l_from TEXT, l_type TEXT, l_to TEXT);
CREATE TABLE wt_dates (d_file INTEGER, d_gid TEXT, d_fact TEXT, d_year INTEGER);
"""

INDIVIDUS = [
    # id, sexe, nom complet, prénoms, nom de famille, naissance
    ("I1", "M", "Jean /Babin/", "Jean", "Babin", 1700),
    ("I2", "F", "Marie /Léger/", "Marie", "Léger", 1705),
    ("I3", "M", "Pierre /Babin/", "Pierre", "Babin", 1726),
    ("I4", "F", "Anne /Babin/", "Anne", "Babin", None),
    ("I5", "F", "Anne /Comeau/", "Anne", "Comeau", 1730),
    ("I6", "M", "Joseph /Babin/", "Joseph", "Babin", 1752),
    ("I7", "F", "Cécile /Thibodeau/", "Cécile", "Thibodeau", None),
]
FAMILLES = [("F1", "I1", "I2"), ("F2", "I3", "I5"), ("F3", None, "I7")]
ENFANTS = [("F1", "I3"), ("F1", "I4"), ("F2", "I6")]
MARIAGES = [("F1", 1725), ("F2", 1750)]


def creer(arbre: int = 1) -> sqlite3.Connection:
    """Crée la mini-base et renvoie la connexion SQLite."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO wt_gedcom VALUES (?, ?)", (arbre, "BABIN"))
    for xref, sexe, nom, givn, surn, naissance in INDIVIDUS:
        conn.execute("INSERT INTO wt_individuals VALUES (?, ?, ?, ?)",
                     (xref, arbre, sexe, f"0 @{xref}@ INDI\n1 NAME {nom}"))
        conn.execute("INSERT INTO wt_name VALUES (?, ?, 0, 'NAME', ?, ?, ?)",
                     (arbre, xref, nom, givn, surn))
        if naissance:
            conn.execute("INSERT INTO wt_dates VALUES (?, ?, 'BIRT', ?)",
                         (arbre, xref, naissance))
    for fam, husb, wife in FAMILLES:
        conn.execute("INSERT INTO wt_families VALUES (?, ?, ?, ?)", (fam, arbre, husb, wife))
        for conjoint in (husb, wife):
            if conjoint:
                conn.execute("INSERT INTO wt_link VALUES (?, ?, 'FAMS', ?)",
                             (arbre, conjoint, fam))
                conn.execute("INSERT INTO wt_link VALUES (?, ?, ?, ?)",
                             (arbre, fam, "HUSB" if conjoint == husb else "WIFE", conjoint))
    for fam, enfant in ENFANTS:
        conn.execute("INSERT INTO wt_link VALUES (?, ?, 'FAMC', ?)", (arbre, enfant, fam))
        conn.execute("INSERT INTO wt_link VALUES (?, ?, 'CHIL', ?)", (arbre, fam, enfant))
    for fam, annee in MARIAGES:
        conn.execute("INSERT INTO wt_dates VALUES (?, ?, 'MARR', ?)", (arbre, fam, annee))
    conn.commit()
    return conn


def faux_run_query(sql, params=None, conn=None):
    """Remplace `db.run_query` : exécute la requête MySQL sur la base SQLite."""
    return pd.read_sql(sql.replace("%s", "?"), conn, params=tuple(params or ()))
