"""
Trouver les erreurs de saisie dans la base.

Les valeurs qui n'ont pas de sens, par exemple :
  - une DATE qui a été tapée dans la colonne des LIEUX (ex. "1820")
  - une année impossible (an 0, an 9999, dans le futur)
  - une naissance APRÈS un décès
  - un âge de décès absurde (plus de 120 ans)
  - des chiffres ajoutés au NOM d'une personne

# TODO / À FAIRE :
  - une personne qui est née avant ses enfants, ou qqch de similaire (regarder la ascendance/descendance)
  - baptême avant naissance ou décès
  - etc.

Ce script NE MODIFIE PAS la base de données. Il ne fait que lire.

Ce script n'est pas fini (03/07/2026).
"""

import datetime

import pandas as pd

from db import get_connection, run_query, t

ANNEE_COURANTE = datetime.date.today().year
FICHIER_SORTIE = "erreurs_a_corriger.txt"

# Pour chaque 'rapport' d'erreur
COLONNES = ["verification", "tree_id", "record_id", "valeur", "type_record", "champ"]

def _vide():
    return pd.DataFrame(columns=COLONNES)

def lieux_ressemblant_a_des_dates(conn):
    """Lieux qui contiennent une année (4 chiffres)"""
    sql = f"""
        SELECT p_file AS tree_id, p_id AS record_id, p_place AS valeur
        FROM `{t('places')}`
        WHERE p_place REGEXP '[12][0-9]{{3}}'
    """
    df = run_query(sql, conn=conn)
    if df.empty:
        return _vide()
    df["verification"] = "Lieu contenant une année"
    df["champ"] = "places.p_place"
    df["type_record"] = "lieu"
    return df[COLONNES]


def lieux_avec_chiffres(conn):
    """Lieux contenant n'importe quel chiffre"""
    sql = f"""
        SELECT p_file AS tree_id, p_id AS record_id, p_place AS valeur
        FROM `{t('places')}`
        WHERE p_place REGEXP '[0-9]'
          AND p_place NOT REGEXP '[12][0-9]{{3}}'
    """
    df = run_query(sql, conn=conn)
    if df.empty:
        return _vide()
    df["verification"] = "Lieu contenant des chiffres"
    df["champ"] = "places.p_place"
    df["type_record"] = "lieu"
    return df[COLONNES]


def annees_impossibles(conn):
    """Années hors de l'intervalle plausible, ou mois/jour invalides."""
    sql = f"""
        SELECT d_file AS tree_id, d_gid AS record_id, d_fact,
               d_day, d_mon, d_year
        FROM `{t('dates')}`
        WHERE (d_year <> 0 AND (d_year < 1400 OR d_year > {ANNEE_COURANTE + 1}))
           OR d_mon > 12
           OR d_day > 31
    """
    df = run_query(sql, conn=conn)
    if df.empty:
        return _vide()
    df["verification"] = "Date impossible"
    df["champ"] = "dates (" + df["d_fact"].astype(str) + ")"
    df["valeur"] = (
        df["d_year"].astype(str) + "-" + df["d_mon"].astype(str) + "-" + df["d_day"].astype(str)
    )
    df["type_record"] = "date"
    return df[COLONNES]


def naissance_apres_deces(conn):
    """Personnes dont la date de naissance est postérieure à la date de décès."""
    # jb c'est la date de naissance et jd c'est la date de décès
    # on regarde les dates dans le même arbre qui ont le même record_id pour trouver les dates de naissance et de décès correspondantes.
    sql = f"""
        SELECT b.d_file AS tree_id, b.d_gid AS record_id,
               b.d_year AS annee_naissance, d.d_year AS annee_deces,
               b.d_julianday1 AS jb, d.d_julianday1 AS jd
        FROM `{t('dates')}` b
        JOIN `{t('dates')}` d
          ON b.d_file = d.d_file AND b.d_gid = d.d_gid
        WHERE b.d_fact = 'BIRT' AND d.d_fact = 'DEAT'
          AND b.d_julianday1 > 0 AND d.d_julianday1 > 0
          AND b.d_julianday1 > d.d_julianday1
    """
    df = run_query(sql, conn=conn)
    if df.empty:
        return _vide()
    df["verification"] = "Naissance après décès"
    df["champ"] = "dates BIRT/DEAT"
    df["valeur"] = "naissance " + df["annee_naissance"].astype(str) + " / décès " + df["annee_deces"].astype(str)
    df["type_record"] = "date"
    return df[COLONNES]

def age_au_deces_improbable(conn, limite=120):
    """Personnes mortes à plus de `limite` ans (plus de 120 ans, par exemple)"""
    # jb c'est la date de naissance et jd c'est la date de décès
    sql = f"""
        SELECT b.d_file AS tree_id, b.d_gid AS record_id,
               b.d_year AS annee_naissance, d.d_year AS annee_deces,
               (d.d_julianday1 - b.d_julianday1) / 365.25 AS age
        FROM `{t('dates')}` b
        JOIN `{t('dates')}` d
          ON b.d_file = d.d_file AND b.d_gid = d.d_gid
        WHERE b.d_fact = 'BIRT' AND d.d_fact = 'DEAT'
          AND b.d_julianday1 > 0 AND d.d_julianday1 > 0
          AND (d.d_julianday1 - b.d_julianday1) / 365.25 > {limite}
    """
    df = run_query(sql, conn=conn)
    if df.empty:
        return _vide()
    df["verification"] = f"Âge au décès > {limite} ans"
    df["champ"] = "dates BIRT/DEAT"
    df["valeur"] = (
        df["age"].round(0).astype(int).astype(str)
        + " ans (n. " + df["annee_naissance"].astype(str)
        + ", d. " + df["annee_deces"].astype(str) + ")"
    )
    df["type_record"] = "date"
    return df[COLONNES]


def noms_avec_chiffres(conn):
    """Noms de personnes contenant des chiffres (date collée dans le nom ?)."""
    sql = f"""
        SELECT n_file AS tree_id, n_id AS record_id, n_full AS valeur
        FROM `{t('name')}`
        WHERE n_type = 'NAME' AND n_full REGEXP '[0-9]'
    """
    df = run_query(sql, conn=conn)
    if df.empty:
        return _vide()
    df["verification"] = "Nom contenant des chiffres"
    df["champ"] = "name.n_full"
    df["type_record"] = "name"
    return df[COLONNES]


# TODO / À FAIRE : Créer une fonction pour vérifier si une personne est née après ses enfants
# TODO / À FAIRE : Créer une fonction pour vérifier si une personne est née avant ses parents
# TODO / À FAIRE : Créer une fonction pour créer les liens de web pour aller sur le page web de la personne

def main():
    conn = get_connection()

    verifications = [
        ("Lieux ~ dates", lieux_ressemblant_a_des_dates),
        ("Lieux ~ chiffres", lieux_avec_chiffres),
        ("Années impossibles", annees_impossibles),
        ("Naissance>Décès", naissance_apres_deces),
        ("Âge improbable", age_au_deces_improbable),
        ("Noms ~ chiffres", noms_avec_chiffres),
    ]

    resultats = {}
    resume = []
    for nom_onglet, fonction in verifications:
        print(f"Vérification : {nom_onglet} ...")
        
        try:
            df = fonction(conn)
        except Exception as e: 
            print(f"Erreur pendant '{nom_onglet}': {e}")
            df = _vide()
            
        resultats[nom_onglet] = df
        resume.append({"verification": nom_onglet, "nb_problemes": len(df)})
        print(f"   -> {len(df)} cas trouvés")

    conn.close()

    df_resume = pd.DataFrame(resume)
    print("\n" + df_resume.to_string(index=False))

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("RÉSUMÉ\n")
        f.write(df_resume.to_string(index=False))
        f.write("\n")
        for nom_onglet, df in resultats.items():
            f.write("\n" + "=" * 50 + "\n")
            f.write(f"{nom_onglet} ({len(df)} cas)\n")
            f.write("=" * 50 + "\n")
            if df.empty:
                f.write("Aucun cas trouvé.\n")
            else:
                f.write(df.to_string(index=False))
                f.write("\n")

    print("\n" + "-" * 50)
    print(f"SUCCÈS : erreurs écrites dans {FICHIER_SORTIE}")


if __name__ == "__main__":
    main()
