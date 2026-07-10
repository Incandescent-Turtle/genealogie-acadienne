"""
Statistiques générales (moyennes) sur la base WebTrees, séparées par sexe.

  - Durée de vie        
  - Âge au 1er mariage
  - Âge à la naissance du 1er enfant
  - Âge à la naissance du dernier enfant
  - Âge au baptême (BAPM)
  - Âge au christening (CHR)
  - Nombre d'enfants par personne

Ce script NE MODIFIE PAS la base de données. Il ne fait que lire.
"""

import datetime
import sys

import pandas as pd

from db import get_connection, run_query, t

FICHIER_SORTIE = "rapports/statistiques.md"
JOURS_PAR_AN = 365.25

FAIT_NAISSANCE = "BIRT"
FAIT_DECES = "DEAT"
FAIT_MARIAGE = "MARR"
FAIT_BAPTEME = "BAPM"
FAIT_CHRISTENING = "CHR"
LIEN_CONJOINT = "FAMS"
LIEN_ENFANT = "CHIL"

AGREGATS_AUTORISES = {"MIN", "MAX"}


def _sql_naissance():
    """Trouver la date de naissance. Utilisé dans la plupart des requêtes."""
    return f"""(
        SELECT d_file, d_gid, MIN(d_julianday1) AS jour
        FROM `{t('dates')}`
        WHERE d_fact = %s AND d_julianday1 > 0
        GROUP BY d_file, d_gid
    )"""


def duree_vie(conn):
    # Trouver la date de naissance et de décès correspondantes, puis calculer la durée de vie.
    sql = f"""
        SELECT b.d_file AS tree_id, b.d_gid AS person_id, i.i_sex AS sexe,
               (d.jour - b.jour) / {JOURS_PAR_AN} AS valeur
        FROM {_sql_naissance()} b
        JOIN (
            SELECT d_file, d_gid, MIN(d_julianday1) AS jour
            FROM `{t('dates')}`
            WHERE d_fact = %s AND d_julianday1 > 0
            GROUP BY d_file, d_gid
        ) d ON d.d_file = b.d_file AND d.d_gid = b.d_gid
        JOIN `{t('individuals')}` i ON i.i_file = b.d_file AND i.i_id = b.d_gid
    """
    return run_query(sql, params=(FAIT_NAISSANCE, FAIT_DECES), conn=conn)


def age_premier_mariage(conn):
    # Trouver la date du premier mariage, puis calculer l'âge au mariage, et noter le sexe.
    sql = f"""
        SELECT b.d_file AS tree_id, b.d_gid AS person_id, i.i_sex AS sexe,
               (m.jour - b.jour) / {JOURS_PAR_AN} AS valeur
        FROM {_sql_naissance()} b
        JOIN (
            SELECT sp.l_file, sp.l_from AS person, MIN(md.d_julianday1) AS jour
            FROM `{t('link')}` sp
            JOIN `{t('dates')}` md
              ON md.d_file = sp.l_file AND md.d_gid = sp.l_to
             AND md.d_fact = %s AND md.d_julianday1 > 0
            WHERE sp.l_type = %s
            GROUP BY sp.l_file, sp.l_from
        ) m ON m.l_file = b.d_file AND m.person = b.d_gid
        JOIN `{t('individuals')}` i ON i.i_file = b.d_file AND i.i_id = b.d_gid
    """
    return run_query(sql, params=(FAIT_NAISSANCE, FAIT_MARIAGE, LIEN_CONJOINT), conn=conn)


def _age_enfant(conn, agregat):
    """Âge du parent à la naissance de son enfant (premier = MIN, dernier = MAX)."""
    
    # Pour permettre d'utiliser MIN ou MAX, mais pas d'autres fonctions SQL.
    if agregat not in AGREGATS_AUTORISES:
        raise ValueError(f"Agrégat non autorisé : {agregat!r}")

    # Trouver les personnes qui sont conjoints, puis les enfants de ces personnes, puis la date de naissance de ces enfants, puis calculer l'âge du parent à la naissance de son enfant.
    sql = f"""
        SELECT b.d_file AS tree_id, b.d_gid AS person_id, i.i_sex AS sexe,
               (c.jour - b.jour) / {JOURS_PAR_AN} AS valeur
        FROM {_sql_naissance()} b
        JOIN (
            SELECT sp.l_file, sp.l_from AS parent, {agregat}(cb.d_julianday1) AS jour
            FROM `{t('link')}` sp
            JOIN `{t('link')}` ch
              ON ch.l_file = sp.l_file AND ch.l_from = sp.l_to AND ch.l_type = %s
            JOIN `{t('dates')}` cb
              ON cb.d_file = ch.l_file AND cb.d_gid = ch.l_to
             AND cb.d_fact = %s AND cb.d_julianday1 > 0
            WHERE sp.l_type = %s
            GROUP BY sp.l_file, sp.l_from
        ) c ON c.l_file = b.d_file AND c.parent = b.d_gid
        JOIN `{t('individuals')}` i ON i.i_file = b.d_file AND i.i_id = b.d_gid
    """
    return run_query(sql, params=(FAIT_NAISSANCE, LIEN_ENFANT, FAIT_NAISSANCE, LIEN_CONJOINT), conn=conn,)


def age_premier_enfant(conn):
    return _age_enfant(conn, "MIN")


def age_dernier_enfant(conn):
    return _age_enfant(conn, "MAX")


def _age_a_evenement(conn, fait):
    """Âge (années) au plus ancien événement `fait` daté, depuis la naissance."""
    
    # e = plus ancienne date de l'événement voulu (baptême OU christening).
    sql = f"""
        SELECT b.d_file AS tree_id, b.d_gid AS person_id, i.i_sex AS sexe,
               (e.jour - b.jour) / {JOURS_PAR_AN} AS valeur
        FROM {_sql_naissance()} b
        JOIN (
            SELECT d_file, d_gid, MIN(d_julianday1) AS jour
            FROM `{t('dates')}`
            WHERE d_fact = %s AND d_julianday1 > 0
            GROUP BY d_file, d_gid
        ) e ON e.d_file = b.d_file AND e.d_gid = b.d_gid
        JOIN `{t('individuals')}` i ON i.i_file = b.d_file AND i.i_id = b.d_gid
    """
    return run_query(sql, params=(FAIT_NAISSANCE, fait), conn=conn)


def age_bapteme(conn):
    return _age_a_evenement(conn, FAIT_BAPTEME)


def age_christening(conn):
    return _age_a_evenement(conn, FAIT_CHRISTENING)


def nombre_enfants(conn):
    # Pour chaque personne conjoint, on compte les enfants distincts de toutes ses familles.
    sql = f"""
        SELECT sp.l_file AS tree_id, sp.l_from AS person_id, i.i_sex AS sexe,
               COUNT(DISTINCT ch.l_to) AS valeur
        FROM `{t('link')}` sp
        JOIN `{t('link')}` ch
          ON ch.l_file = sp.l_file AND ch.l_from = sp.l_to AND ch.l_type = %s
        JOIN `{t('individuals')}` i ON i.i_file = sp.l_file AND i.i_id = sp.l_from
        WHERE sp.l_type = %s
        GROUP BY sp.l_file, sp.l_from, i.i_sex
    """
    return run_query(sql, params=(LIEN_ENFANT, LIEN_CONJOINT), conn=conn)

CRITERES = [
    {"nom": "Durée de vie",                         "fn": duree_vie,            "unite": "ans",     "min": 0,  "max": 120},
    {"nom": "Âge au 1er mariage",                   "fn": age_premier_mariage,  "unite": "ans",     "min": 12, "max": 100},
    {"nom": "Âge à la naissance du 1er enfant",     "fn": age_premier_enfant,   "unite": "ans",     "min": 12, "max": 80},
    {"nom": "Âge à la naissance du dernier enfant", "fn": age_dernier_enfant,   "unite": "ans",     "min": 12, "max": 80},
    {"nom": "Âge au baptême (BAPM)",                "fn": age_bapteme,          "unite": "ans",     "min": 0,  "max": 100},
    {"nom": "Âge au christening (CHR)",             "fn": age_christening,      "unite": "ans",     "min": 0,  "max": 100},
    {"nom": "Nombre d'enfants",                     "fn": nombre_enfants,       "unite": "enfants", "min": 0,  "max": 30},
]

ORDRE_SEXE = {"F": 0, "M": 1, "U": 2}
SEXE_LISIBLE = {"F": "Femmes", "M": "Hommes", "U": "Inconnu"}

def resumer(nom, df, unite, bornes):
    """Renvoie un bloc Markdown : titre + tableau pour une mesure."""
    
    lignes = [f"## {nom} ({unite})", ""]
    if df.empty:
        lignes.append("_Aucune donnée._")
        return lignes

    bmin, bmax = bornes
    len_avant = len(df)
    # Filtrer les valeurs hors bornes.
    df = df[(df["valeur"] >= bmin) & (df["valeur"] <= bmax)]
    ecartes = len_avant - len(df)
    if ecartes:
        lignes.append(f"_{ecartes} valeurs écartées (hors {bmin}–{bmax} {unite})._")
        lignes.append("")

    lignes.append("| Sexe | Nombre | Moyenne | Médiane |")
    lignes.append("|------|-------:|--------:|--------:|")

    def _ligne(etiquette, serie):
        return (f"| {etiquette} | {len(serie):,} | "
                f"{serie.mean():.1f} | {serie.median():.1f} |")

    lignes.append(_ligne("Tous", df["valeur"]))
    sexes = sorted(df["sexe"].dropna().unique(),
                   key=lambda s: ORDRE_SEXE.get(s, 99))
    for sexe in sexes:
        etiquette = SEXE_LISIBLE.get(sexe, str(sexe))
        lignes.append(_ligne(etiquette, df.loc[df["sexe"] == sexe, "valeur"]))
    return lignes


def main():
    conn = get_connection()
    try:
        sorties = []
        for m in CRITERES:
            print(f"Calcul : {m['nom']} ...")
            try:
                df = m["fn"](conn)
            except Exception as e:
                print(f"  Erreur : {e}")
                df = pd.DataFrame(columns=["tree_id", "person_id", "sexe", "valeur"])
            sorties.append(resumer(m["nom"], df, m["unite"], (m["min"], m["max"])))
    finally:
        conn.close()

    date = datetime.date.today().isoformat()
    entete = [
        "# Statistiques généalogiques (par sexe)",
        "",
        f"_Généré le {date} depuis la base WebTrees._",
        "",
        "Les valeurs hors bornes plausibles sont écartées comme erreurs de saisie.",
    ]
    blocs = [entete] + sorties
    rapport = "\n\n".join("\n".join(bloc) for bloc in blocs) + "\n"

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write(rapport)

if __name__ == "__main__":
    main()
