"""
Chargement des `Personne` depuis la base de données.

Construit les objets `Personne` (voir `commun/modele.py` : nom, sexe, faits
datés, mariages, parents, enfants, conjoints) utilisés par le reste du pipeline.

Le chargement se fait EN LOT pour rester rapide : au lieu d'une requête par
personne, on télécharge tout un arbre en quelques requêtes `IN (...)`.

Étapes (`charger_groupe`) :
  1. regrouper les identifiants demandés par arbre
  2. pour chaque arbre, lire en lot : nom + sexe (+ prénoms, nom de famille,
     autres noms), faits datés (année ; date complète + lieu depuis le GEDCOM
     brut), mariages, puis
     les liens (parents, enfants, conjoints)
  3. charger d'un coup les proches (on garde leur nom + année de naissance)
  4. assembler le tout en objets `Personne`

Les requêtes sont découpées en morceaux de `TAILLE_LOT_SQL` identifiants.

À ajouter :
  - charger plus d'informations sur les proches (pas seulement la naissance),
    pour permettre une comparaison plus fine des ascendants/descendants

Grace aux lots, ce script est très rapide. On pourrait faire millions de comparaisons sans problème, dans quelques minutes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator

import pandas as pd

from ..commun.gedcom import Evenement, evenements_gedcom
from ..commun.modele import Faits, Mariage, Personne, Proche
from ..commun.noms import normaliser
from .db import run_query, t

if TYPE_CHECKING:
    from .db import Connexion

# Faits datés qui concernent une personne
FAITS_PERSONNE = ("BIRT", "BAPM", "CHR", "DEAT", "BURI")

# Valeurs que WebTrees met dans n_givn / n_surn quand la partie est inconnue
NOMS_INCONNUS = {"@P.N.", "@N.M."}

# Nombre d'identifiants par requête `IN (...)`
TAILLE_LOT_SQL = 500

def _annee(valeur: Any) -> int | None:
    """Convertit une année SQL en int ou None."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return None
    return int(valeur)


def _xref_ou_none(valeur: Any) -> str | None:
    """Un xref SQL (str) ou None s'il est vide / NULL / NaN."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return None
    valeur = str(valeur).strip()
    return valeur or None


def _nettoyer_xrefs(xrefs: Iterable[str]) -> list[str]:
    """Enlève les vides et les doublons en gardant l'ordre."""
    vus, propres = set(), []
    for x in xrefs:
        if x and str(x).strip() and x not in vus:
            vus.add(x)
            propres.append(x)
    return propres

def _morceaux(sequence: list[Any], taille: int = TAILLE_LOT_SQL) -> Iterator[list[Any]]:
    """Découpe une séquence en morceaux d'au plus `taille` éléments."""
    for i in range(0, len(sequence), taille):
        yield sequence[i:i + taille]


def _lire_par_morceaux(
    conn: Connexion,
    sql_pour: Callable[[str, tuple], tuple[str, tuple]],
    ids: Iterable[str],
) -> pd.DataFrame:
    """Exécute une requête `IN (...)` par morceau d'ids et concatène le tout.

    `sql_pour(marques, morceau)` renvoie le couple `(sql, params)` pour un
    morceau, où `marques` est la liste de `%s` correspondante.
    """
    frames = []
    for morceau in _morceaux(list(ids)):
        marques = ",".join(["%s"] * len(morceau))
        sql, params = sql_pour(marques, morceau)
        frames.append(run_query(sql, params=params, conn=conn))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _grouper_premier(df: pd.DataFrame, cle: str, valeur: Callable[[Any], Any]) -> dict[Any, Any]:
    """{ligne[cle]: valeur(ligne)}, en gardant la première occurrence de `cle`.
    
    Exemple :
    {
        "123": "John Doe",
        "456": "Jane Doe",
        "789": "Jim Doe",
    }
    signifie que la personne 123 est John Doe, et on ignorait les autres noms de 123.
    """
    resultat = {}
    for r in df.itertuples():
        k = getattr(r, cle)
        if k not in resultat:
            resultat[k] = valeur(r)
    return resultat


def _grouper_xrefs(df: pd.DataFrame, cle: str, colonnes: tuple[str, ...]) -> dict[Any, list[str]]:
    """{ligne[cle]: [xrefs des `colonnes`...]}, dédoublonnés et nettoyés.
    
    Exemple :
    {
        "123": ["456", "789"],
        "456": ["123", "789"],
        "789": ["123", "456"],
    }
    signifie que la personne 123 est lié à les personnes 456 et 789 (ils peuvent être les parents, par exemple).
    """
    resultat = {}
    for r in df.itertuples():
        resultat.setdefault(getattr(r, cle), []).extend(getattr(r, c) for c in colonnes)
    return {k: _nettoyer_xrefs(v) for k, v in resultat.items()}


def _partie_nom(valeur: Any) -> str:
    """Une partie de nom (GIVN / SURN) nettoyée ; "" si vide ou inconnue."""
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return ""
    valeur = " ".join(str(valeur).replace("/", " ").split())
    return "" if valeur in NOMS_INCONNUS else valeur


def _base_lot(
    conn: Connexion, tree_id: int, xrefs: Iterable[str]
) -> dict[str, tuple[str, str, str, str]]:
    """Nom complet, sexe, prénoms et nom de famille pour un lot.
    Renvoie {xref: (nom, sexe, prenoms, nom_famille)} (premier NAME, par n_num)."""
    def sql_pour(marques, morceau):
        return f"""
            SELECT n.n_id AS xref,
                   TRIM(REPLACE(n.n_full, '/', '')) AS nom,
                   i.i_sex AS sexe,
                   n.n_givn AS givn,
                   n.n_surn AS surn
            FROM `{t('name')}` n
            JOIN `{t('individuals')}` i
              ON n.n_file = i.i_file AND n.n_id = i.i_id
            WHERE n.n_file = %s AND n.n_type = 'NAME' AND n.n_id IN ({marques})
            ORDER BY n.n_id, n.n_num
        """, (tree_id, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, xrefs)
    return _grouper_premier(
        df, "xref", lambda r: (r.nom, r.sexe, _partie_nom(r.givn), _partie_nom(r.surn)))


def _autres_noms_lot(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, list[str]]:
    """Tous les noms d'un lot, dans l'ordre (NAME d'abord, puis par n_num).
    Renvoie {xref: [nom, ...]} ; le premier est le nom principal."""
    def sql_pour(marques, morceau):
        return f"""
            SELECT n_id AS xref, TRIM(REPLACE(n_full, '/', '')) AS nom
            FROM `{t('name')}`
            WHERE n_file = %s AND n_id IN ({marques})
            ORDER BY n_id, CASE WHEN n_type = 'NAME' THEN 0 ELSE 1 END, n_num
        """, (tree_id, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, xrefs)
    resultat: dict[str, list[str]] = {}
    for r in df.itertuples():
        resultat.setdefault(r.xref, []).append(" ".join(str(r.nom or "").split()))
    return resultat


def _noms_alternatifs(nom: str, tous: list[str]) -> list[str]:
    """Les autres noms d'une personne : sans le nom principal, sans doublons
    (après normalisation), dans l'ordre."""
    vus = {normaliser(nom)}
    autres = []
    for n in tous:
        cle = normaliser(n)
        if cle and cle not in vus:
            vus.add(cle)
            autres.append(n)
    return autres


def _faits_lot(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, Faits]:
    """Faits datés pour un lot. Renvoie {xref: Fait}."""
    marques_faits = ",".join(["%s"] * len(FAITS_PERSONNE))

    def sql_pour(marques, morceau):
        return f"""
            SELECT d_gid AS xref, d_fact AS fait, MIN(NULLIF(d_year, 0)) AS annee
            FROM `{t('dates')}`
            WHERE d_file = %s AND d_gid IN ({marques}) AND d_fact IN ({marques_faits})
            GROUP BY d_gid, d_fact
        """, (tree_id, *morceau, *FAITS_PERSONNE)
    df = _lire_par_morceaux(conn, sql_pour, xrefs)
    resultat = {}
    for r in df.itertuples():
        resultat.setdefault(r.xref, {})[r.fait] = _annee(r.annee)
    return resultat


def _gedcom_lot(
    conn: Connexion, tree_id: int, ids: Iterable[str], table: str = "individuals",
    faits: tuple[str, ...] = FAITS_PERSONNE,
) -> dict[str, dict[str, Evenement]]:
    """Date complète + lieu des événements, lus dans le GEDCOM brut.

    `table` = "individuals" (i_gedcom) ou "families" (f_gedcom).
    Renvoie {id: {fait: {date, lieu}}}."""
    prefixe = {"individuals": "i", "families": "f"}[table]

    def sql_pour(marques, morceau):
        return f"""
            SELECT {prefixe}_id AS id, {prefixe}_gedcom AS gedcom
            FROM `{t(table)}`
            WHERE {prefixe}_file = %s AND {prefixe}_id IN ({marques})
        """, (tree_id, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, ids)
    return _grouper_premier(df, "id", lambda r: evenements_gedcom(r.gedcom, faits))


def _parents_lot(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, list[str]]:
    """Xrefs des parents pour un lot. Renvoie {xref: [xref_parent, ...]}."""
    def sql_pour(marques, morceau):
        return f"""
            SELECT lk.l_from AS xref, fam.f_husb AS pere, fam.f_wife AS mere
            FROM `{t('families')}` fam
            JOIN `{t('link')}` lk
              ON lk.l_file = fam.f_file AND lk.l_to = fam.f_id AND lk.l_type = 'FAMC'
            WHERE lk.l_file = %s AND lk.l_from IN ({marques})
        """, (tree_id, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, xrefs)
    return _grouper_xrefs(df, "xref", ("pere", "mere"))


def _enfants_lot(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, list[str]]:
    """Xrefs des enfants pour un lot. Renvoie {xref: [xref_enfant, ...]}."""
    def sql_pour(marques, morceau):
        return f"""
            SELECT sp.l_from AS xref, enf.l_to AS enfant
            FROM `{t('link')}` sp
            JOIN `{t('link')}` enf
              ON enf.l_file = sp.l_file AND enf.l_from = sp.l_to AND enf.l_type = 'CHIL'
            WHERE sp.l_file = %s AND sp.l_from IN ({marques}) AND sp.l_type = 'FAMS'
        """, (tree_id, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, xrefs)
    return _grouper_xrefs(df, "xref", ("enfant",))


def _conjoints_lot(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, list[str]]:
    """Xrefs des conjoints pour un lot. Renvoie {xref: [xref_conjoint, ...]}."""
    ens = {str(x) for x in xrefs}

    def sql_pour(marques, morceau):
        return f"""
            SELECT f_husb AS husb, f_wife AS wife
            FROM `{t('families')}`
            WHERE f_file = %s AND (f_husb IN ({marques}) OR f_wife IN ({marques}))
        """, (tree_id, *morceau, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, xrefs)
    resultat = {}
    for r in df.itertuples():
        if r.husb in ens and r.wife:
            resultat.setdefault(r.husb, []).append(r.wife)
        if r.wife in ens and r.husb:
            resultat.setdefault(r.wife, []).append(r.husb)
    return {x: _nettoyer_xrefs(v) for x, v in resultat.items()}


def _noms_lot(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, str]:
    """Nom complet pour un lot d'identifiants. Renvoie {xref: nom}."""
    def sql_pour(marques, morceau):
        return f"""
            SELECT n_id AS xref, TRIM(REPLACE(n_full, '/', '')) AS nom
            FROM `{t('name')}`
            WHERE n_file = %s AND n_type = 'NAME' AND n_id IN ({marques})
        """, (tree_id, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, xrefs)
    return _grouper_premier(df, "xref", lambda r: r.nom)


def _naissances_lot(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, Proche]:
    """Nom + année de naissance pour un lot (proches).
    Renvoie {xref: {nom, nom_norm, naissance}}."""
    def sql_pour(marques, morceau):
        return f"""
            SELECT n.n_id AS xref,
                   TRIM(REPLACE(n.n_full, '/', '')) AS nom,
                   (SELECT MIN(NULLIF(d.d_year, 0))
                      FROM `{t('dates')}` d
                     WHERE d.d_file = n.n_file AND d.d_gid = n.n_id
                       AND d.d_fact = 'BIRT') AS naissance
            FROM `{t('name')}` n
            WHERE n.n_file = %s AND n.n_type = 'NAME' AND n.n_id IN ({marques})
        """, (tree_id, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, xrefs)
    return _grouper_premier(df, "xref", lambda r: {
        "nom": r.nom, "nom_norm": normaliser(r.nom), "naissance": _annee(r.naissance),
        "person_id": str(r.xref),
    })


def _annees_mariage_lot(conn: Connexion, tree_id: int, fam_ids: Iterable[str]) -> dict[str, int | None]:
    """Année de mariage (MARR) pour un lot de familles. Renvoie {fam: annee}."""
    def sql_pour(marques, morceau):
        return f"""
            SELECT d_gid AS fam, MIN(NULLIF(d_year, 0)) AS annee
            FROM `{t('dates')}`
            WHERE d_file = %s AND d_gid IN ({marques}) AND d_fact = 'MARR'
            GROUP BY d_gid
        """, (tree_id, *morceau)
    df = _lire_par_morceaux(conn, sql_pour, fam_ids)
    return _grouper_premier(df, "fam", lambda r: _annee(r.annee))


def _mariages_lot(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, list[Mariage]]:
    """Mariages (année + conjoint) pour un lot.
    Renvoie {xref: [{annee, conjoint, conjoint_norm, conjoint_id, date, lieu}, ...]}."""
    def sql_pour(marques, morceau):
        return f"""
            SELECT sp.l_from AS xref,
                   fam.f_id AS fam,
                   CASE WHEN fam.f_husb = sp.l_from THEN fam.f_wife
                        ELSE fam.f_husb END AS conjoint_id
            FROM `{t('families')}` fam
            JOIN `{t('link')}` sp
              ON sp.l_file = fam.f_file AND sp.l_to = fam.f_id AND sp.l_type = 'FAMS'
            WHERE sp.l_file = %s AND sp.l_from IN ({marques})
        """, (tree_id, *morceau)
    familles = _lire_par_morceaux(conn, sql_pour, xrefs)
    if familles.empty:
        return {}

    fam_ids = familles["fam"].dropna().unique().tolist()
    annees = _annees_mariage_lot(conn, tree_id, fam_ids)
    evenements = _gedcom_lot(conn, tree_id, fam_ids, table="families", faits=("MARR",))
    noms = _noms_lot(conn, tree_id, familles["conjoint_id"].dropna().unique().tolist())

    resultat: dict[str, list[Mariage]] = {}
    for r in familles.itertuples():
        marr = evenements.get(r.fam, {}).get("MARR", {})
        conjoint = (noms.get(r.conjoint_id) or "").strip() or None
        resultat.setdefault(r.xref, []).append({
            "annee": annees.get(r.fam),
            "conjoint": conjoint,
            "conjoint_norm": normaliser(conjoint) if conjoint else None,
            "conjoint_id": _xref_ou_none(r.conjoint_id),
            "date": marr.get("date"),
            "lieu": marr.get("lieu"),
        })
    return resultat


def _charger_arbre(conn: Connexion, tree_id: int, xrefs: Iterable[str]) -> dict[str, Personne]:
    """Charge en lot toutes les personnes d'un même arbre. 
    Renvoie {xref: Personne}."""
    xrefs = _nettoyer_xrefs(xrefs)
    base = _base_lot(conn, tree_id, xrefs)
    tous_noms = _autres_noms_lot(conn, tree_id, xrefs)
    faits = _faits_lot(conn, tree_id, xrefs)
    evenements = _gedcom_lot(conn, tree_id, xrefs)
    mariages = _mariages_lot(conn, tree_id, xrefs)
    # charger les liens comme xrefs
    liens = {
        "parents": _parents_lot(conn, tree_id, xrefs),
        "enfants": _enfants_lot(conn, tree_id, xrefs),
        "conjoints": _conjoints_lot(conn, tree_id, xrefs),
    }

    # charger tous les proches (parents + enfants + conjoints) en une seule fois
    a_charger = {x for d in liens.values() for liste in d.values() for x in liste}
    # on charge les dates de naissance des proches ici; dans le futur on pourrait charger plus d'information sur les proches ici.
    proches = _naissances_lot(conn, tree_id, list(a_charger))

    def resoudre(role, xref):
        return [proches[x] for x in liens[role].get(xref, []) if x in proches]

    return {
        xref: Personne(
            tree_id=tree_id,
            person_id=xref,
            nom_complet=nom,
            nom_norm=normaliser(nom),
            sexe=sexe,
            faits=faits.get(xref, {}),
            mariages=mariages.get(xref, []),
            parents=resoudre("parents", xref),
            enfants=resoudre("enfants", xref),
            conjoints=resoudre("conjoints", xref),
            prenoms=prenoms,
            nom_famille=nom_famille,
            noms_alternatifs=_noms_alternatifs(nom, tous_noms.get(xref, [])),
            dates={f: e["date"] for f, e in evenements.get(xref, {}).items() if e["date"]},
            lieux={f: e["lieu"] for f, e in evenements.get(xref, {}).items() if e["lieu"]},
        )
        for xref, (nom, sexe, prenoms, nom_famille) in base.items()
    }


def charger_groupe(
    conn: Connexion, gens: Iterable[tuple[Any, Any]]
) -> dict[tuple[int, str], Personne]:
    """Charge en lot toutes les personnes `gens` (itérable de `(tree_id, person_id)`).

    On regroupe par arbre et on ne fait que quelques requêtes par arbre. 
    
    Renvoie {(tree_id, person_id): Personne}."""
    par_arbre: dict[int, list[str]] = {}
    for tree_id, person_id in gens:
        par_arbre.setdefault(int(tree_id), []).append(str(person_id))

    personnes: dict[tuple[int, str], Personne] = {}
    for tree_id, xrefs in par_arbre.items():
        for xref, p in _charger_arbre(conn, tree_id, xrefs).items():
            personnes[(tree_id, xref)] = p
    return personnes


def charger_personne(conn: Connexion, tree_id: int, person_id: str) -> Personne:
    """Charge une seule personne (raccourci sur `charger_groupe`)."""
    personnes = charger_groupe(conn, [(tree_id, person_id)])
    cle = (int(tree_id), str(person_id))
    if cle not in personnes:
        raise ValueError(f"Personne introuvable : arbre {tree_id}, id {person_id}")
    return personnes[cle]
