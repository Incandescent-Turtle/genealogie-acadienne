"""
Charger deux personnes depuis la base et les comparer (exemple / débogage).

    python -m genealogie_acadienne.pipeline.comparer_paire [--parquet DOSSIER]
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from ..commun.comparaison import RapportComplet, afficher_comparaison, comparer
from ..commun.modele import Personne
from ..donnees.personnes import charger_personne
from ..donnees.source_parquet import ajouter_option_parquet, ouvrir_connexion

if TYPE_CHECKING:
    from ..donnees.db import Connexion


def comparer_ids(
    conn: Connexion, tree_a: int, id_a: str, tree_b: int, id_b: str
) -> tuple[Personne, Personne, RapportComplet]:
    """Charge deux personnes par leurs identifiants et les compare."""
    a = charger_personne(conn, tree_a, id_a)
    b = charger_personne(conn, tree_b, id_b)
    return a, b, comparer(a, b)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Comparer deux personnes (exemple).")
    ajouter_option_parquet(parser)
    with ouvrir_connexion(parser.parse_args(argv).parquet) as conn:
        a, b, rapport = comparer_ids(conn, 34, "I0669", 6, "1590")
    afficher_comparaison(a, b, rapport)


if __name__ == "__main__":
    main()
