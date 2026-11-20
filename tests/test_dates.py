"""Dates GEDCOM (aucune base)."""

import pytest

from genealogie_acadienne.commun.dates import (
    DateGedcom, analyser_date, annee, compatibles, decaler_date, ecart_annees, formater_date)


@pytest.mark.parametrize("texte, attendu", [
    ("1745", DateGedcom(1745)),
    ("MAR 1745", DateGedcom(1745, 3)),
    ("12 MAR 1745", DateGedcom(1745, 3, 12)),
    ("abt 12 mar 1745", DateGedcom(1745, 3, 12, "environ")),
    ("EST 1745", DateGedcom(1745, None, None, "environ")),
    ("BEF 1745", DateGedcom(1745, None, None, "avant")),
    ("AFT 1745", DateGedcom(1745, None, None, "apres")),
    ("BET 1740 AND 1745", DateGedcom(1740, None, None, "entre", 1745)),
    ("FROM 1740 TO 1745", DateGedcom(1740, None, None, "entre", 1745)),
    ("1745/46", DateGedcom(1745)),
    ("3 AOUT 1755", DateGedcom(1755, 8, 3)),
])
def test_analyser(texte, attendu):
    assert analyser_date(texte) == attendu


@pytest.mark.parametrize("texte", [None, "", "Y", "vers la fin", "12 XYZ 1745", "BET 1740"])
def test_illisible(texte):
    assert analyser_date(texte) is None


def test_ecarts():
    assert ecart_annees(analyser_date("1745"), analyser_date("1748")) == 3
    assert ecart_annees(analyser_date("ABT 1745"), analyser_date("1747")) == 0
    assert ecart_annees(analyser_date("BET 1740 AND 1745"), analyser_date("1750")) == 5
    assert ecart_annees(None, analyser_date("1750")) is None
    assert compatibles(analyser_date("1745"), analyser_date("1747")) is True
    assert compatibles(analyser_date("1745"), analyser_date("1750")) is False
    assert annee("ABT 3 MAR 1700") == 1700 and annee(None) is None


def test_formater_et_decaler():
    assert formater_date(analyser_date("abt 12 mar 1745")) == "ABT 12 MAR 1745"
    assert decaler_date("12 MAR 1745", 3) == "12 MAR 1748"
    assert decaler_date("BET 1740 AND 1745", -2) == "BET 1738 AND 1743"
    assert decaler_date("illisible", 3) == "illisible"
