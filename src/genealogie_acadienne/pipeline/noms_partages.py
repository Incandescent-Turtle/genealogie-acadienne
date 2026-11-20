"""
Exporter un résumé des noms partagés entre arbres.

    python -m genealogie_acadienne.pipeline.noms_partages   # -> temp/partages_resume.csv
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..commun.noms import trouver_noms_partages
from ..donnees.db import load_env_file
from ..donnees.noms import charger_personnes

if TYPE_CHECKING:
    import pandas as pd


def exporter_resume(partages: pd.DataFrame, fichier: str = "temp/partages_resume.csv") -> None:
    """Écrit un résumé : une ligne par nom partagé (groupe)."""
    resume = (partages.groupby("groupe_id")
              .agg(nom_norm=("nom_norm", "first"),
                   n_personnes=("n_personnes", "first"),
                   n_arbres=("n_arbres", "first"))
              .reset_index())
    resume.to_csv(fichier, index=False, encoding="utf-8")
    print(f"{len(resume)} noms partagés -> {fichier}")


def main() -> None:
    load_env_file(override=True)
    df = charger_personnes()
    print(f"{len(df)} personnes chargées.\n")

    partages = trouver_noms_partages(df)
    exporter_resume(partages)


if __name__ == "__main__":
    main()
