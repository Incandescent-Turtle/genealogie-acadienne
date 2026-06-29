"""
Correspondances par les NOMS — version simple.
"""

import unicodedata

from db import get_connection, run_query, t


def normaliser(texte):
    """Minuscules, sans accents ni ponctuation, espaces compactés."""
    if texte is None:
        return ""
    texte = unicodedata.normalize("NFKD", str(texte))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.lower()
    texte = "".join(c if c.isalnum() or c.isspace() else " " for c in texte)
    return " ".join(texte.split())


def charger_personnes(conn=None):
    """Charge toutes les personnes : arbre, identifiant, nom complet."""
    df = run_query(
        f"""
        SELECT n_file AS tree_id,
               n_id   AS person_id,
               TRIM(REPLACE(n_full, '/', '')) AS nom_complet
        FROM `{t('name')}`
        WHERE n_type = 'NAME'
        """,
        conn=conn,
    )
    df = df.drop_duplicates(subset=["tree_id", "person_id"]).reset_index(drop=True)
    df["nom_norm"] = df["nom_complet"].map(normaliser)
    return df

def chercher_meme_nom(df, nom_complet, tree_id):
    """Renvoie les personnes de l'arbre `tree_id` au nom exactement identique."""
    cible = normaliser(nom_complet)
    sous = df[df["tree_id"] == tree_id]
    return sous[sous["nom_norm"] == cible]


# exemple d'utilisation
if __name__ == "__main__":
    df = charger_personnes()
    print(f"{len(df)} personnes chargées.\n")

    # 1. On pique une personne (ici la première de la liste).
    personne = df.iloc[0]
    print(f"Personne choisie : {personne['nom_complet']} "
          f"(arbre {personne['tree_id']}, id {personne['person_id']})")

    # 2. On choisit un autre arbre.
    autres_arbres = sorted(a for a in df["tree_id"].unique()
                           if a != personne["tree_id"])
    arbre_cible = autres_arbres[0]
    print(f"Arbre ciblé : {arbre_cible}\n")

    # 3. On cherche le même nom dans cet arbre.
    resultats = chercher_meme_nom(df, personne["nom_complet"], arbre_cible)
    if resultats.empty:
        print("Aucune personne du même nom dans cet arbre.")
    else:
        print(f"{len(resultats)} personne(s) du même nom :")
        for _, r in resultats.iterrows():
            print(f"  {r['nom_complet']}  (id {r['person_id']})")
