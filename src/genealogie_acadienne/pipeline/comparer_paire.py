"""
Charger deux personnes depuis la base et les comparer (exemple / débogage).

    python -m genealogie_acadienne.pipeline.comparer_paire
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..commun.comparaison import RapportComplet, afficher_comparaison, comparer
from ..commun.modele import Personne
from ..donnees.db import get_connection, load_env_file
from ..donnees.personnes import charger_personne

if TYPE_CHECKING:
    from pymysql.connections import Connection


def comparer_ids(
    conn: Connection, tree_a: int, id_a: str, tree_b: int, id_b: str
) -> tuple[Personne, Personne, RapportComplet]:
    """Charge deux personnes par leurs identifiants et les compare."""
    a = charger_personne(conn, tree_a, id_a)
    b = charger_personne(conn, tree_b, id_b)
    return a, b, comparer(a, b)


def main() -> None:
    load_env_file(override=True)
    conn = get_connection()
    try:
        a, b, rapport = comparer_ids(conn, 34, "I0669", 6, "1590")
    finally:
        conn.close()
    afficher_comparaison(a, b, rapport)


if __name__ == "__main__":
    main()
