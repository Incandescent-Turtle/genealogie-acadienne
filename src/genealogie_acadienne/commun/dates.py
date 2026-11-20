"""
Lire, comparer et décaler les dates GEDCOM (« ABT 12 MAR 1745 », « BET 1740 AND 1745 »).

`Personne.faits` ne garde que l'année ; `Personne.dates` garde le texte GEDCOM
complet. Ce module transforme ce texte en `DateGedcom` (année, mois, jour,
qualificatif, et année de fin pour les intervalles).

Formats reconnus (GEDCOM 5.5.1, mois en anglais, plus les mois français
courants dans les saisies manuelles) :
  1745 · MAR 1745 · 12 MAR 1745 · ABT/EST/CAL 1745 · BEF/AFT 1745 ·
  BET 1740 AND 1745 · FROM 1740 TO 1745 · 1745/46 (double datation)
Tout le reste donne `None`. Module pur : aucune base.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

MOIS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    # français (saisies manuelles)
    "JANV": 1, "FEVR": 2, "FEV": 2, "MARS": 3, "AVR": 4, "MAI": 5, "JUIN": 6,
    "JUIL": 7, "AOUT": 8, "AOU": 8, "SEPT": 9, "DECE": 12,
}
MOIS_GEDCOM = {v: k for k, v in list(MOIS.items())[:12]}

# Qualificatifs : "exact", "environ" (ABT/EST/CAL), "avant", "apres", "entre".
QUALIFICATIFS = {"ABT": "environ", "EST": "environ", "CAL": "environ",
                 "BEF": "avant", "AFT": "apres"}


@dataclass(frozen=True)
class DateGedcom:
    """Une date GEDCOM lue. `annee_fin` sert aux intervalles (BET / FROM)."""
    annee: int
    mois: int | None = None
    jour: int | None = None
    qualificatif: str = "exact"
    annee_fin: int | None = None

    @property
    def bornes(self) -> tuple[int, int]:
        """Intervalle d'années plausible (inclusif), selon le qualificatif."""
        if self.qualificatif == "entre" and self.annee_fin is not None:
            return self.annee, self.annee_fin
        if self.qualificatif == "environ":
            return self.annee - 2, self.annee + 2
        if self.qualificatif == "avant":
            return self.annee - 10, self.annee
        if self.qualificatif == "apres":
            return self.annee, self.annee + 10
        return self.annee, self.annee


_SIMPLE = re.compile(r"^(?:(\d{1,2})\s+)?(?:([A-Z]{3,4})\.?\s+)?(\d{3,4})(?:/\d{1,2})?$")


def _date_simple(texte: str) -> tuple[int, int | None, int | None] | None:
    """« 12 MAR 1745 », « MAR 1745 », « 1745 », « 1745/46 » -> (annee, mois, jour)."""
    m = _SIMPLE.match(texte.strip())
    if not m:
        return None
    jour, mois, annee = m.groups()
    if mois is not None and mois not in MOIS:
        return None
    return int(annee), (MOIS[mois] if mois else None), (int(jour) if jour else None)


def analyser_date(texte: str | None) -> DateGedcom | None:
    """Lit une date GEDCOM. Renvoie None si elle est vide ou illisible."""
    if not texte:
        return None
    t = " ".join(str(texte).upper().replace(",", " ").split())
    t = t.replace("É", "E").replace("Û", "U")
    for prefixe, fin in (("BET ", " AND "), ("FROM ", " TO ")):
        if t.startswith(prefixe) and fin in t:
            a, b = t[len(prefixe):].split(fin, 1)
            da, db = _date_simple(a), _date_simple(b)
            if da and db:
                return DateGedcom(da[0], da[1], da[2], "entre", db[0])
            return None
    if t.startswith("FROM "):
        t = t[5:]
    qualificatif = "exact"
    mots = t.split(" ", 1)
    if mots[0] in QUALIFICATIFS and len(mots) == 2:
        qualificatif, t = QUALIFICATIFS[mots[0]], mots[1]
    simple = _date_simple(t)
    if simple is None:
        return None
    return DateGedcom(simple[0], simple[1], simple[2], qualificatif)


def annee(texte: str | None) -> int | None:
    """L'année d'une date GEDCOM, ou None."""
    d = analyser_date(texte)
    return d.annee if d else None


def ecart_annees(a: DateGedcom | None, b: DateGedcom | None) -> int | None:
    """Écart minimal en années entre deux dates, compte tenu des qualificatifs
    (0 si les intervalles plausibles se chevauchent). None si une date manque."""
    if a is None or b is None:
        return None
    (a0, a1), (b0, b1) = a.bornes, b.bornes
    return max(0, max(a0, b0) - min(a1, b1))


def compatibles(a: DateGedcom | None, b: DateGedcom | None, tolerance: int = 2) -> bool | None:
    """Les deux dates peuvent-elles désigner le même événement ? None si inconnu."""
    ecart = ecart_annees(a, b)
    return None if ecart is None else ecart <= tolerance


def formater_date(d: DateGedcom | None) -> str | None:
    """Réécrit une `DateGedcom` en texte GEDCOM."""
    if d is None:
        return None
    def simple(an: int, mois: int | None, jour: int | None) -> str:
        parties = [str(jour)] if jour else []
        if mois:
            parties.append(MOIS_GEDCOM[mois])
        return " ".join(parties + [str(an)])
    if d.qualificatif == "entre" and d.annee_fin is not None:
        return f"BET {simple(d.annee, d.mois, d.jour)} AND {d.annee_fin}"
    prefixe = {"environ": "ABT ", "avant": "BEF ", "apres": "AFT "}.get(d.qualificatif, "")
    return prefixe + simple(d.annee, d.mois, d.jour)


def decaler_date(texte: str | None, annees: int) -> str | None:
    """Décale une date GEDCOM de `annees` ans (le texte illisible est rendu tel quel)."""
    d = analyser_date(texte)
    if d is None:
        return texte
    fin = d.annee_fin + annees if d.annee_fin is not None else None
    return formater_date(replace(d, annee=d.annee + annees, annee_fin=fin))
