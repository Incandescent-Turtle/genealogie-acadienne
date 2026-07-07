"""
Examiner les personnes qui partegent un même nom et les apparier selon nos métriques.

On sauvegarde uniquement les paires avec au moins `--min-criteres` correspondances (1 par défaut

Pour ces paires, on conserve toutes les données afin de :
  - se rappeler qu'elles ont été traitées
  - voir ce qu'elles ont en commun
  - pouvoir les filtrer plus tard (par ex. 7+ correspondances)

Comme il y a beaucoup de noms, on peut fixer une LIMITE de comparaisons.
"""

import argparse
from itertools import combinations

from comparer_personnes import charger_personne, comparer
from correspondances_noms import charger_personnes, trouver_noms_partages
from db import execute, get_connection, t

# Pour chaque métrique, les verdicts qui comptent comme une "concordance".
# (voir comparer_personnes.py pour la liste des verdicts possibles)
VERDICTS_POSITIFS = {
    "naissance": {"identique", "proche"},
    "bapteme": {"identique", "proche"},
    "deces": {"identique", "proche"},
    "sepulture": {"identique", "proche"},
    "mariage": {"identique", "proche", "meme_conjoint"},
    # "periode_estimee": {"chevauchement", "proche"}, # ça aide à idenifier, mais c'est créé par rapport aux dates connues, qui sont déjà les autres métriques.
    "ascendants": {"communs"},
    "descendants": {"communs"},
}

# Table où l'on enregistre les comparaisons
TABLE_COMPARAISONS = "person_comparisons"

# Colonnes de la table, dans l'ordre utilisé pour l'INSERT.
COLONNES = [
    "tree_id_a", "person_id_a", "tree_id_b", "person_id_b",
    "n_criteria", "criteria",
    "birth_verdict", "birth_gap",
    "baptism_verdict", "baptism_gap",
    "death_verdict", "death_gap",
    "burial_verdict", "burial_gap",
    "marriage_verdict", "marriage_n_shared_names",
    "marriage_n_exact", "marriage_n_close",
    "period_verdict", "period_gap", # estimées
    "ancestors_verdict", "ancestors_n_shared",
    "descendants_verdict", "descendants_n_shared",
]

# Colonnes qui identifient la paire
CLES = ("tree_id_a", "person_id_a", "tree_id_b", "person_id_b")

def criteres_concordants(rapport):
    """Liste des métriques où les deux personnes concordent."""
    concordants = []
    for nom, r in rapport.items():
        if r["verdict"] in VERDICTS_POSITIFS.get(nom, set()):
            concordants.append(nom)
    return concordants


def creer_table(conn):
    """Crée la table des comparaisons si elle n'existe pas encore.

    La clé unique sur la paire permet d'éviter les doublons
    """
    sql = f"""
        CREATE TABLE IF NOT EXISTS `{TABLE_COMPARAISONS}` (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tree_id_a INT NOT NULL,
            person_id_a VARCHAR(32) NOT NULL,
            tree_id_b INT NOT NULL,
            person_id_b VARCHAR(32) NOT NULL,
            n_criteria INT NOT NULL DEFAULT 0,
            criteria TEXT,
            birth_verdict VARCHAR(16),
            birth_gap INT,
            baptism_verdict VARCHAR(16),
            baptism_gap INT,
            death_verdict VARCHAR(16),
            death_gap INT,
            burial_verdict VARCHAR(16),
            burial_gap INT,
            marriage_verdict VARCHAR(16),
            marriage_n_shared_names INT,
            marriage_n_exact INT,
            marriage_n_close INT,
            period_verdict VARCHAR(16),
            period_gap INT,
            ancestors_verdict VARCHAR(16),
            ancestors_n_shared INT,
            descendants_verdict VARCHAR(16),
            descendants_n_shared INT,
            comparison_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uniq_pair (tree_id_a, person_id_a, tree_id_b, person_id_b)
        ) CHARACTER SET utf8mb4
    """
    execute(sql, conn=conn)


def _sql_insert():
    """Construit l'INSERT ... ON DUPLICATE KEY UPDATE pour une comparaison"""
    cols = ", ".join(f"`{c}`" for c in COLONNES)
    marques = ", ".join(["%s"] * len(COLONNES))
    maj = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in COLONNES if c not in CLES)
    return (f"INSERT INTO `{TABLE_COMPARAISONS}` ({cols}) VALUES ({marques}) "
            f"ON DUPLICATE KEY UPDATE {maj}")


def rapport_en_ligne(pa, pb, rapport, concordants):
    """Aplati une comparaison en une ligne (tuple) prête pour l'INSERT."""
    mariage = rapport["mariage"]
    valeurs = {
        "tree_id_a": int(pa.tree_id), "person_id_a": str(pa.person_id),
        "tree_id_b": int(pb.tree_id), "person_id_b": str(pb.person_id),
        "n_criteria": len(concordants),
        "criteria": ", ".join(concordants),
        "birth_verdict": rapport["naissance"]["verdict"],
        "birth_gap": rapport["naissance"]["ecart"],
        "baptism_verdict": rapport["bapteme"]["verdict"],
        "baptism_gap": rapport["bapteme"]["ecart"],
        "death_verdict": rapport["deces"]["verdict"],
        "death_gap": rapport["deces"]["ecart"],
        "burial_verdict": rapport["sepulture"]["verdict"],
        "burial_gap": rapport["sepulture"]["ecart"],
        "marriage_verdict": mariage["verdict"],
        "marriage_n_shared_names": mariage["n_noms_communs"],
        "marriage_n_exact": mariage["n_exacts"],
        "marriage_n_close": mariage["n_proches"],
        "period_verdict": rapport["periode_estimee"]["verdict"],
        "period_gap": rapport["periode_estimee"]["ecart"],
        "ancestors_verdict": rapport["ascendants"]["verdict"],
        "ancestors_n_shared": rapport["ascendants"]["n_communs"],
        "descendants_verdict": rapport["descendants"]["verdict"],
        "descendants_n_shared": rapport["descendants"]["n_communs"],
    }
    return tuple(valeurs[c] for c in COLONNES)


def _ordonner(pa, pb):
    """Ordre canonique d'une paire pour éviter les doublons (A,B) vs (B,A).
        On trie par (arbre, identifiant)"""
    cle_a = (int(pa.tree_id), str(pa.person_id))
    cle_b = (int(pb.tree_id), str(pb.person_id))
    return (pa, pb) if cle_a <= cle_b else (pb, pa)


def construire_paires(partages, limite=None):
    """Toutes les paires de personnes à comparer (même nom, arbres différents).
    On ignore les paires du même arbre
    On respecte l'ordre canonique, et la limite."""
    paires = []
    for _, groupe in partages.groupby("groupe_id"):
        gens = list(groupe.itertuples(index=False))
        # toutes les paires possibles entre les personnes du groupe
        for pa, pb in combinations(gens, 2):
            if pa.tree_id == pb.tree_id:
                continue  # même arbre : on saute
            paires.append(_ordonner(pa, pb))
            if limite is not None and len(paires) >= limite:
                return paires
    return paires


def charger_personne_cache(conn, cache, tree_id, person_id):
    """Charge une personne en la mettant en cache (chargée une seule fois)."""
    cle = (int(tree_id), str(person_id))
    if cle not in cache:
        cache[cle] = charger_personne(conn, *cle)
    return cache[cle]


def enregistrer_lot(conn, sql_insert, lot):
    """Enregistre un lot de comparaisons puis le vide.
    Renvoie le nombre de lignes enregistrées."""
    if not lot:
        return 0
    execute(sql_insert, params=lot, conn=conn, many=True)
    n = len(lot)
    lot.clear()
    return n


def apparier(conn, limite=None, min_criteres=1, criteres_signal=4, taille_lot=500):
    """Importer les nomes partagés et les apparier selon nos métriques.

    On n'enregistre que les paires ayant au moins `min_criteres` critères
    concordants

    Renvoie le couple `(enregistres, trouves)`.
    """
    creer_table(conn)
    sql_insert = _sql_insert()

    # charger les noms partagés
    df = charger_personnes(conn)
    print(f"{len(df)} personnes chargées.")
    partages = trouver_noms_partages(df)
    print(f"{partages['groupe_id'].nunique()} noms partagés.")

    # préparer les paires à comparer
    paires = construire_paires(partages, limite)
    total = len(paires)
    print(f"{total} comparaisons à faire (enregistrées dans `{TABLE_COMPARAISONS}`).\n")
    if total == 0:
        return 0, 0

    # Comparer et enregistrer chaque comparaison, par lots
    cache = {}  # on ne charge chaque personne qu'une seule fois
    seuil = max(1, total // 100)  # pour afficher l'avancement tous les ~1 %
    lot = []
    enregistres = trouves = 0

    for i, (pa, pb) in enumerate(paires, 1):
        try:
            a = charger_personne_cache(conn, cache, pa.tree_id, pa.person_id)
            b = charger_personne_cache(conn, cache, pb.tree_id, pb.person_id)
        except ValueError:
            continue

        rapport = comparer(a, b)
        concordants = criteres_concordants(rapport)
        if len(concordants) >= min_criteres:
            lot.append(rapport_en_ligne(pa, pb, rapport, concordants))

        if len(lot) >= taille_lot:
            enregistres += enregistrer_lot(conn, sql_insert, lot)

        # avancement tous les ~1 %
        if i % seuil == 0 or i == total:
            pct = round(100 * i / total)
            print(f"... {pct}% ({i}/{total}), "
                  f"{enregistres + len(lot)} enregistrées, "
                  f"{trouves} avec >= {criteres_signal} critères")

    enregistres += enregistrer_lot(conn, sql_insert, lot)
    print(f"\nTerminé : {enregistres} comparaisons enregistrées dans `{TABLE_COMPARAISONS}` ({trouves} avec >= {criteres_signal} critères).")
    return enregistres, trouves

def main():
    conn = get_connection()
    try:
        apparier(conn,limite=None, min_criteres=1, criteres_signal=4, taille_lot=500)
    finally:
        conn.close()

if __name__ == "__main__":
    main()