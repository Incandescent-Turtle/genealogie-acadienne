"""Lecture des événements dans un GEDCOM brut (module pur)."""

from __future__ import annotations

from genealogie_acadienne import evenements_gedcom

GEDCOM = """0 @I1@ INDI
1 NAME Jean /Babin/
2 GIVN Jean
1 SEX M
1 BIRT
2 DATE ABT 12 MAR 1745
2 PLAC Grand-Pré,
3 CONC  Acadie
2 SOUR @S1@
3 PAGE p. 12
1 BAPM
2 DATE 14 MAR 1745
1 BIRT
2 DATE 1746
1 DEAT Y
1 BURI
2 PLAC Saint-Charles-des-Mines
"""


def test_evenements():
    ev = evenements_gedcom(GEDCOM)
    # première occurrence de BIRT seulement ; la SOUR/PAGE ne gêne pas
    assert ev["BIRT"] == {"date": "ABT 12 MAR 1745", "lieu": "Grand-Pré, Acadie"}
    assert ev["BAPM"] == {"date": "14 MAR 1745", "lieu": None}
    assert ev["DEAT"] == {"date": None, "lieu": None}
    assert ev["BURI"] == {"date": None, "lieu": "Saint-Charles-des-Mines"}
    assert "NAME" in ev  # sans filtre, tous les faits de niveau 1


def test_filtre_et_vide():
    assert set(evenements_gedcom(GEDCOM, ("BIRT", "BURI"))) == {"BIRT", "BURI"}
    assert evenements_gedcom(None) == {} and evenements_gedcom("") == {}
    assert evenements_gedcom("1 BIRT\r\n2 DATE 1700\r\n") == {"BIRT": {"date": "1700", "lieu": None}}
