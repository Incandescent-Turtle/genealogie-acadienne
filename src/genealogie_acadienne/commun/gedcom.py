"""
Lire les événements (date + lieu) dans le texte GEDCOM brut d'un enregistrement.

WebTrees garde le GEDCOM complet de chaque individu (`i_gedcom`) et de chaque
famille (`f_gedcom`). La table `dates` ne donne que l'année ; la table
`placelinks` ne dit pas à quel événement appartient un lieu. Le GEDCOM brut,
lui, a les deux :

    1 BIRT
    2 DATE ABT 12 MAR 1745
    2 PLAC Grand-Pré, Acadie

Module pur : aucune base, aucune entrée/sortie.
"""

from __future__ import annotations

from typing import TypedDict


class Evenement(TypedDict):
    """La date (texte GEDCOM tel quel, ex. « ABT 1745 ») et le lieu d'un événement."""
    date: str | None
    lieu: str | None


def evenements_gedcom(texte: str | None, faits: tuple[str, ...] | None = None) -> dict[str, Evenement]:
    """Renvoie {fait: {date, lieu}} pour les événements de niveau 1 du GEDCOM.

    On garde la PREMIÈRE occurrence de chaque fait (comme le nom principal).
    `faits` limite les faits lus (ex. ("BIRT", "DEAT")) ; None = tous.
    Les lignes de continuation (CONC / CONT) d'un lieu sont recollées.
    """
    resultat: dict[str, Evenement] = {}
    if not texte:
        return resultat

    courant: Evenement | None = None
    dernier: str | None = None  # "date" ou "lieu", pour CONC / CONT
    for ligne in str(texte).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        morceaux = ligne.strip().split(" ", 2)
        if len(morceaux) < 2 or not morceaux[0].isdigit():
            continue
        niveau, etiquette = int(morceaux[0]), morceaux[1]
        brut = morceaux[2].rstrip() if len(morceaux) > 2 else ""  # CONC garde l'espace de tête
        valeur = brut.strip()

        if niveau == 1:
            dernier = None
            if (faits is None or etiquette in faits) and etiquette not in resultat:
                courant = {"date": None, "lieu": None}
                resultat[etiquette] = courant
            else:
                courant = None
        elif courant is None or niveau < 2:
            continue
        elif niveau == 2 and etiquette == "DATE":
            courant["date"] = valeur or None
            dernier = "date"
        elif niveau == 2 and etiquette == "PLAC":
            courant["lieu"] = valeur or None
            dernier = "lieu"
        elif niveau == 3 and etiquette in ("CONC", "CONT") and dernier:
            suite = brut if etiquette == "CONC" else " " + valeur
            courant[dernier] = ((courant[dernier] or "") + suite).strip() or None
        elif niveau == 2:
            dernier = None
    return resultat
