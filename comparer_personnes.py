"""
Comparer DEUX personnes pour décider si c'est la même.

Après que `correspondances_noms.py` a trouvé des gens qui portent le même nom,
On les compare ici en utilisant les métriques suivantes : 
naissance, baptême, décès, sépulture, mariage, ascendants, descendants, conjoints, et période de vie.

Principe (modulaire) :
  1. on charge chaque personne UNE fois -> objet `Personne` (faits + proches) ;
  2. chaque métrique est une fonction séparée `comparer_xxx(a, b)` qui explore
     une seule chose et renvoie un petit rapport (valeurs + verdict) ;
  3. `comparer(a, b)` rassemble toutes les métriques.

On compare les proches par leur NOM normalisé et les dates par ANNÉE. 
Si une date manque, on estime la période de vie à partir des proches (et des dates connues).

Maintenant, quand on regard les parents ou les enfants, on regarde seulmente les nom and les dates de naissance.
Une meilleure stratégie consisterait à examiner tous les faits concernant ces personnes, à l'exception des enfants et des parents (parce que ça serait un cercle).
"""

from dataclasses import dataclass, field

import pandas as pd

from correspondances_noms import normaliser
from db import get_connection, run_query, t

# Faits datés qui concernent une personne
FAITS_PERSONNE = ("BIRT", "BAPM", "CHR", "DEAT", "BURI")
ECART_GENERATION = 28  # âge typique d'un parent à la naissance d'un enfant
ECART_MARIAGE = 28     # années entre une naissance et le mariage
MARGE_PERIODE = 40     # écart max toléré entre deux périodes de vie estimées

@dataclass
class Personne:
    tree_id: int
    person_id: str
    nom_complet: str
    nom_norm: str
    sexe: str
    faits: dict     # {"BIRT": 1700, "DEAT": 1750, ...}
    mariages: list = field(default_factory=list)   # années de mariage
    parents: list = field(default_factory=list)    # [{nom, nom_norm, naissance}]
    enfants: list = field(default_factory=list)
    conjoints: list = field(default_factory=list)

    def __str__(self):
        return (f"{self.nom_complet} (arbre {self.tree_id}, id {self.person_id})")

def _annee(valeur):
    """Convertit une année SQL en int ou None."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return None
    return int(valeur)

def _faits(conn, tree_id, xref):
    """Année de chaque fait daté de la personne (BIRT, BAPM, DEAT...).
    Renvoie un dictionnaire {fait: année, fait2: année2, ...}."""
    marques = ",".join(["%s"] * len(FAITS_PERSONNE))
    sql = f"""
        SELECT d_fact AS fait, MIN(NULLIF(d_year, 0)) AS annee
        FROM `{t('dates')}`
        WHERE d_file = %s AND d_gid = %s AND d_fact IN ({marques})
        GROUP BY d_fact
    """
    df = run_query(sql, params=(tree_id, xref, *FAITS_PERSONNE), conn=conn)
    return {r.fait: _annee(r.annee) for r in df.itertuples()}

def _parents_xrefs(conn, tree_id, xref):
    """Identifiants du père et de la mère d'une personne.
    Renvoie une liste avec les xrefs des parents (commençant par le père puis la mère).
    Exemple : [xref1, xref2]"""
    sql = f"""
        SELECT fam.f_husb AS pere, fam.f_wife AS mere
        FROM `{t('families')}` fam
        JOIN `{t('link')}` lk
          ON lk.l_file = fam.f_file AND lk.l_to = fam.f_id AND lk.l_type = 'FAMC'
        WHERE lk.l_file = %s AND lk.l_from = %s
    """
    df = run_query(sql, params=(tree_id, xref), conn=conn)
    xrefs = df["pere"].tolist() + df["mere"].tolist()
    return _nettoyer_xrefs(xrefs)

def _enfants_xrefs(conn, tree_id, xref):
    """Identifiants des enfants (familles où la personne est conjoint).
    Renvoie une liste avec les xrefs des enfants.
    Exemple : [xref1, xref2]"""
    sql = f"""
        SELECT enf.l_to AS enfant
        FROM `{t('link')}` sp
        JOIN `{t('link')}` enf
          ON enf.l_file = sp.l_file AND enf.l_from = sp.l_to AND enf.l_type = 'CHIL'
        WHERE sp.l_file = %s AND sp.l_from = %s AND sp.l_type = 'FAMS'
    """
    df = run_query(sql, params=(tree_id, xref), conn=conn)
    return _nettoyer_xrefs(df["enfant"].tolist())

def _conjoints_xrefs(conn, tree_id, xref):
    """Identifiants des conjoints (l'autre époux des familles communes).<
    Renvoie une liste avec les xrefs des conjoints.
    Exemple : [xref1, xref2, ...]"""
    # Trouver le xref de chaque conjoint
    sql = f"""
        SELECT CASE WHEN f_husb = %s THEN f_wife ELSE f_husb END AS conjoint
        FROM `{t('families')}`
        WHERE f_file = %s AND (f_husb = %s OR f_wife = %s)
    """
    df = run_query(sql, params=(xref, tree_id, xref, xref), conn=conn)
    return _nettoyer_xrefs(df["conjoint"].tolist())

def _mariages(conn, tree_id, xref):
    """Mariages de la personne : année + conjoint (fait MARR de ses familles).
    Renvoie une liste de dicts {annee, conjoint, conjoint_norm}"""
    
    # Trouver les familles où la personne est conjoint, 
    # puis, trouver l'entrée de ce mariage s'il existe, et noter la date correspondante et le nom du conjoint 
    sql = f"""
        WITH familles AS (
            SELECT DISTINCT
                   fam.f_id   AS fam,
                   fam.f_file AS fichier,
                   CASE WHEN fam.f_husb = %s THEN fam.f_wife
                        ELSE fam.f_husb END AS conjoint_id
            FROM `{t('families')}` fam
            JOIN `{t('link')}` sp
              ON sp.l_file = fam.f_file AND sp.l_to = fam.f_id
             AND sp.l_type = 'FAMS'
            WHERE sp.l_file = %s AND sp.l_from = %s
        )
        SELECT f.fam,
               (SELECT MIN(NULLIF(d.d_year, 0))
                  FROM `{t('dates')}` d
                 WHERE d.d_file = f.fichier AND d.d_gid = f.fam
                   AND d.d_fact = 'MARR') AS annee,
               (SELECT TRIM(REPLACE(n.n_full, '/', ''))
                  FROM `{t('name')}` n
                 WHERE n.n_file = f.fichier AND n.n_id = f.conjoint_id
                   AND n.n_type = 'NAME'
                 LIMIT 1) AS conjoint
        FROM familles f
    """
    df = run_query(sql, params=(xref, tree_id, xref), conn=conn)
    mariages = []
    # Preparer le date et le nom du conjoint pour chaque mariage
    for r in df.itertuples():
        conjoint = (r.conjoint or "").strip() or None
        mariages.append({
            "annee": _annee(r.annee),
            "conjoint": conjoint,
            "conjoint_norm": normaliser(conjoint) if conjoint else None,
        })
    return mariages

def _nettoyer_xrefs(xrefs):
    """Enlève les vides et les doublons en gardant l'ordre."""
    vus, propres = set(), []
    for x in xrefs:
        if x and str(x).strip() and x not in vus:
            vus.add(x)
            propres.append(x)
    return propres

# TODO / À FAIRE : trouver plus d'infos sur les proches, pas seulment les dates de naissance.
def _proches(conn, tree_id, xrefs):
    """Pour une liste d'identifiants : nom complet + année de naissance."""
    if not xrefs:
        return []
    marques = ",".join(["%s"] * len(xrefs))
    # Trouver l'entrée de nom avec le même xref, puis trouver la date de naissance correspondante
    sql = f"""
        SELECT n.n_id AS xref,
               TRIM(REPLACE(n.n_full, '/', '')) AS nom,
               (SELECT MIN(NULLIF(d.d_year, 0))
                  FROM `{t('dates')}` d
                 WHERE d.d_file = n.n_file AND d.d_gid = n.n_id
                   AND d.d_fact = 'BIRT') AS naissance
        FROM `{t('name')}` n
        WHERE n.n_file = %s AND n.n_type = 'NAME' AND n.n_id IN ({marques})
    """
    df = run_query(sql, params=(tree_id, *xrefs), conn=conn)
    return [{"nom": r.nom, "nom_norm": normaliser(r.nom),
             "naissance": _annee(r.naissance)} for r in df.itertuples()]

def charger_personne(conn, tree_id, person_id):
    """Charge une personne et ses proches dans un objet `Personne`."""
    sql = f"""
        SELECT TRIM(REPLACE(n.n_full, '/', '')) AS nom, i.i_sex AS sexe
        FROM `{t('name')}` n
        JOIN `{t('individuals')}` i
          ON n.n_file = i.i_file AND n.n_id = i.i_id
        WHERE n.n_file = %s AND n.n_id = %s AND n.n_type = 'NAME'
        LIMIT 1
    """
    base = run_query(sql, params=(tree_id, person_id), conn=conn)
    if base.empty:
        raise ValueError(f"Personne introuvable : arbre {tree_id}, id {person_id}")
    nom = base.iloc[0]["nom"]

    return Personne(
        tree_id=tree_id,
        person_id=person_id,
        nom_complet=nom,
        nom_norm=normaliser(nom),
        sexe=base.iloc[0]["sexe"],
        faits=_faits(conn, tree_id, person_id),
        mariages=_mariages(conn, tree_id, person_id),
        parents=_proches(conn, tree_id, _parents_xrefs(conn, tree_id, person_id)),
        enfants=_proches(conn, tree_id, _enfants_xrefs(conn, tree_id, person_id)),
        conjoints=_proches(conn, tree_id, _conjoints_xrefs(conn, tree_id, person_id)),
    )

def annee_naissance_estimee(p):
    """Estime l'année de naissance. Renvoie (annee, methode).
    On essaie, dans l'ordre : la vraie naissance, le baptême, puis les proches (enfants, mariage, conjoint, parents), le chr."""
    if p.faits.get("BIRT"):
        return p.faits["BIRT"], "naissance"
    # Le baptême se passe directement après la naissance habituellement.
    if p.faits.get("BAPM"):
        return p.faits.get("BAPM"), "bapteme"

    # Trouver le date de naissance du premier enfant, puis soustraire l'écart de génération.
    annees_enfants = [e["naissance"] for e in p.enfants if e["naissance"]]
    if annees_enfants:
        return min(annees_enfants) - ECART_GENERATION, "via enfants"

    # Trouver le date du premier mariage, puis soustraire l'écart de mariage.
    annees_mariage = [m["annee"] for m in p.mariages if m["annee"]]
    if annees_mariage:
        return min(annees_mariage) - ECART_MARIAGE, "via mariage"

    # Trouver le moyenne des dates de naissance des conjoints.
    annees_conjoint = [c["naissance"] for c in p.conjoints if c["naissance"]]
    if annees_conjoint:
        return round(sum(annees_conjoint) / len(annees_conjoint)), "via conjoint"

    # Trouver le date de naissance du parent le plus âgé, puis ajouter l'écart de génération.
    annees_parents = [r["naissance"] for r in p.parents if r["naissance"]]
    if annees_parents:
        return max(annees_parents) + ECART_GENERATION, "via parents"

    # Le chr se trouve seulment 4 fois dans la base de données.
    if p.faits.get("CHR"):
        return p.faits.get("CHR"), "chr"

    return None, "inconnue"

def periode_active(p):
    """Estime la période où la personne était vivante : (naissance estimée, fin, methode).

    la `fin` est la dernière trace de vie : décès/sépulture, ou la dernière date active connue (mariage, naissance d'un enfant).
    Renvoie (None, None, "inconnue") si on ne sait vraiment rien.
    """
    debut, methode = annee_naissance_estimee(p)

    # Trouver les dates de décès, sépulture, baptême, chr.
    traces = []
    for fait in ("DEAT", "BURI", "BAPM", "CHR"):
        if p.faits.get(fait):
            traces.append(p.faits[fait])
    # Ajouter les dates de mariage, de naissance d'un enfant.
    traces += [m["annee"] for m in p.mariages if m["annee"]]
    traces += [e["naissance"] for e in p.enfants if e["naissance"]]

    fin = max(traces) if traces else debut
    if debut is not None and fin is not None and fin < debut:
        fin = debut
    if debut is None:
        return None, None, "inconnue"
    return debut, fin, methode

def _comparer_annee(ya, yb, proche=3):
    """Compare deux années : verdict identique / proche / different / inconnu."""
    if ya is None or yb is None:
        return {"a": ya, "b": yb, "ecart": None, "verdict": "inconnu"}
    ecart = abs(ya - yb)
    verdict = "identique" if ecart == 0 else "proche" if ecart <= proche else "different"
    return {"a": ya, "b": yb, "ecart": ecart, "verdict": verdict}

def comparer_naissance(a, b, proche=3):
    r = _comparer_annee(a.faits.get("BIRT"), b.faits.get("BIRT"), proche)
    r["metrique"] = "naissance"
    return r

def comparer_deces(a, b, proche=3):
    r = _comparer_annee(a.faits.get("DEAT"), b.faits.get("DEAT"), proche)
    r["metrique"] = "deces"
    return r

def comparer_bapteme(a, b, proche=3):
    ya = a.faits.get("BAPM") or a.faits.get("CHR")
    yb = b.faits.get("BAPM") or b.faits.get("CHR")
    r = _comparer_annee(ya, yb, proche)
    r["metrique"] = "bapteme"
    return r


def comparer_sepulture(a, b, proche=3):
    r = _comparer_annee(a.faits.get("BURI"), b.faits.get("BURI"), proche)
    r["metrique"] = "sepulture"
    return r


# TODO / À FAIRE : Pour comparer les conjoints, on devrait utiliser RapidFuzz ou une comparaison phonétique.
def comparer_mariage(a, b, proche=2):
    """Compare les mariages en regardant l'ANNÉE et le NOM DU CONJOINT.

    Chacun peut avoir plusieurs mariages. On retient la meilleure paire en
    privilégiant d'abord les paires où le conjoint concorde, puis le plus petit écart d'années. 
    Ainsi :
      - même conjoint + même année  -> "identique"
      - même conjoint, année absente/éloignée -> "meme_conjoint"
      - même année mais conjoints DIFFÉRENTS -> "autre_conjoint" (ne prouve pas que c'est la même personne)
      - conjoints inconnus -> on retombe sur la comparaison d'année seule.
    """
    aa, bb = a.mariages, b.mariages
    if not aa or not bb:
        return {"metrique": "mariage", "a": None, "b": None, "ecart": None,
                "conjoint_a": None, "conjoint_b": None,
                "meme_conjoint": False, "verdict": "inconnu"}

    candidats = []
    for ma in aa:
        for mb in bb:
            ya, yb = ma["annee"], mb["annee"]
            ecart = abs(ya - yb) if (ya and yb) else None
            na, nb = ma["conjoint_norm"], mb["conjoint_norm"]
            meme_conjoint = bool(na and nb and na == nb)
            # tri : conjoint concordant d'abord, puis plus petit écart d'année
            cle = (0 if meme_conjoint else 1,
                   ecart if ecart is not None else 9999)
            candidats.append((cle, ecart, meme_conjoint, ma, mb))

    # On trie les candidats par order de priorité qu'on explique (en utilisant le clé)
    _, ecart, meme_conjoint, ma, mb = min(candidats, key=lambda c: c[0])

    # TODO / À FAIRE : Essayer de trouver UN conjoint qui y est commun -- ne pas regarder simplement les premiers conjoints triés.
    if meme_conjoint:
        if ecart == 0:
            verdict = "identique"
        elif ecart is not None and ecart <= proche:
            verdict = "proche"
        else:
            verdict = "meme_conjoint"
    elif ma["conjoint_norm"] and mb["conjoint_norm"]:
        # les deux conjoints sont connus mais différents
        verdict = ("autre_conjoint" if (ecart is not None and ecart <= proche) else "different")
    elif ecart is None:
        verdict = "inconnu"          # conjoints inconnus, années absentes
    elif ecart == 0:
        verdict = "identique"        # conjoints inconnus : on juge sur l'année
    elif ecart <= proche:
        verdict = "proche"
    else:
        verdict = "different"

    return {"metrique": "mariage",
            "a": ma["annee"], "b": mb["annee"], "ecart": ecart,
            "conjoint_a": ma["conjoint"], "conjoint_b": mb["conjoint"],
            "meme_conjoint": meme_conjoint, "verdict": verdict}


def comparer_periode_estimee(a, b, marge=MARGE_PERIODE):
    # Debut et fin de la période de vie estimée
    da, fa, methode_a = periode_active(a)
    db, fb, methode_b = periode_active(b)
    r = {"metrique": "periode_estimee",
         "a": (da, fa) if da is not None else None,
         "b": (db, fb) if db is not None else None,
         "methode_a": methode_a, "methode_b": methode_b}
    if da is None or db is None:
        r["ecart"] = None
        r["verdict"] = "inconnu"
        return r

    # Écart entre les deux intervalles (0 s'ils se chevauchent).
    ecart = max(0, max(da, db) - min(fa, fb))
    r["ecart"] = ecart
    r["verdict"] = ("chevauchement" if ecart == 0 else "proche" if ecart <= marge else "different")
    return r


def _comparer_noms(proches_a, proches_b):
    """Noms en commun entre deux listes de proches (parents, enfants...)."""
    sa = {x["nom_norm"] for x in proches_a if x["nom_norm"]}
    sb = {x["nom_norm"] for x in proches_b if x["nom_norm"]}
    communs = sa & sb
    if not sa or not sb:
        verdict = "inconnu"
    elif communs:
        verdict = "communs"
    else:
        verdict = "aucun_commun"
    return {"n_a": len(sa), "n_b": len(sb),
            "communs": sorted(communs), "n_communs": len(communs),
            "verdict": verdict}


def comparer_ascendants(a, b):
    r = _comparer_noms(a.parents, b.parents)
    r["metrique"] = "ascendants"
    return r

def comparer_descendants(a, b):
    r = _comparer_noms(a.enfants, b.enfants)
    r["metrique"] = "descendants"
    return r


def comparer_conjoints(a, b):
    r = _comparer_noms(a.conjoints, b.conjoints)
    r["metrique"] = "conjoints"
    return r

METRIQUES = (
    comparer_naissance,
    comparer_bapteme,
    comparer_deces,
    comparer_sepulture,
    comparer_mariage,
    comparer_periode_estimee,
    comparer_ascendants,
    comparer_descendants,
    comparer_conjoints,
)


def comparer(a, b):
    """Lance toutes les métriques et renvoie {nom_metrique: rapport}."""
    resultats = {}
    for fn in METRIQUES:
        r = fn(a, b)
        resultats[r["metrique"]] = r
    return resultats


def comparer_ids(conn, tree_a, id_a, tree_b, id_b):
    """Charge deux personnes par leurs identifiants et les compare."""
    a = charger_personne(conn, tree_a, id_a)
    b = charger_personne(conn, tree_b, id_b)
    return a, b, comparer(a, b)


def _intervalle_txt(bornes):
    """Debut-Fin ou juste le debut si c'est la même année."""
    if not bornes:
        return "?"
    debut, fin = bornes
    return f"{debut}" if debut == fin else f"{debut}-{fin}"


def _ecart_txt(ecart):
    """Écart en années, ou vide si inconnu."""
    return "" if ecart is None else f"écart {ecart} an(s)"


def _detail_comparaison(nom, r):
    """Texte propre à chaque type de métrique (noms, intervalle, mariage, année)."""
    if "communs" in r:  # noms (parents, enfants, conjoints)
        communs = f" : {', '.join(r['communs'])}" if r["communs"] else ""
        return f"{r['n_communs']} commun(s){communs} (A={r['n_a']}, B={r['n_b']})"
    if nom == "periode_estimee":  # intervalle
        ecart = "chevauchement" if r["ecart"] == 0 else _ecart_txt(r["ecart"])
        return (f"A={_intervalle_txt(r['a'])} ({r['methode_a']}) "
                f"B={_intervalle_txt(r['b'])} ({r['methode_b']}) {ecart}")
    if nom == "mariage":  # année + conjoint
        ca, cb = r["conjoint_a"] or "?", r["conjoint_b"] or "?"
        return f"A={r['a']} (conj. {ca}) B={r['b']} (conj. {cb}) {_ecart_txt(r['ecart'])}"
    return f"A={r['a']} B={r['b']} {_ecart_txt(r['ecart'])}"  # année simple


def afficher_comparaison(a, b, rapport):
    print(f"A : {a}")
    print(f"B : {b}\n")
    for nom, r in rapport.items():
        print(f"  {nom:16s} [{r['verdict']:14s}] {_detail_comparaison(nom, r)}")


if __name__ == "__main__":
    conn = get_connection()
    try:
        a, b, rapport = comparer_ids(conn, 34, "I0669", 6, "1590")
    finally:
        conn.close()
    afficher_comparaison(a, b, rapport)
