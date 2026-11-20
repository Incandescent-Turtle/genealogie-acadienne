"""Importer le paquet ne doit ouvrir aucune connexion ni lire `.env`,
et `commun` doit rester indépendant de `donnees`, `pipeline`, pandas et pymysql."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

MODULES = [
    "genealogie_acadienne",
    "genealogie_acadienne.commun.modele",
    "genealogie_acadienne.commun.noms",
    "genealogie_acadienne.commun.comparaison",
    "genealogie_acadienne.commun.criteres",
    "genealogie_acadienne.commun.gedcom",
    "genealogie_acadienne.donnees.db",
    "genealogie_acadienne.donnees.noms",
    "genealogie_acadienne.donnees.personnes",
    "genealogie_acadienne.pipeline.apparier_personnes",
    "genealogie_acadienne.pipeline.comparer_paire",
    "genealogie_acadienne.pipeline.noms_partages",
    "genealogie_acadienne.pipeline.statistiques",
    "genealogie_acadienne.pipeline.trouver_erreurs",
]


def _executer(code: str, cwd: Path) -> dict:
    """Lance `code` dans un Python neuf (sans DB_*) et renvoie son JSON final."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("DB_")}
    env["PYTHONPATH"] = str(SRC)
    sortie = subprocess.run([sys.executable, "-c", code], cwd=cwd, env=env,
                            capture_output=True, text=True, check=True)
    return json.loads(sortie.stdout.strip().splitlines()[-1])


def test_import_sans_connexion_ni_env(tmp_path):
    # Un `.env` dans le dossier courant : il ne doit PAS être lu à l'import.
    (tmp_path / ".env").write_text('DB_HOST="ne_pas_lire"\n', encoding="utf-8")
    code = textwrap.dedent(f"""
        import importlib, json, os, socket, sys, warnings
        import pandas  # pandas ajoute ses propres filtres d'avertissement : on l'importe avant
        import pymysql

        appels = []
        def espion(*a, **k):
            appels.append("connect")
            raise RuntimeError("connexion interdite")
        pymysql.connect = espion
        socket.socket.connect = espion

        chemin_avant = list(sys.path)
        filtres_avant = list(warnings.filters)

        for m in {MODULES!r}:
            importlib.import_module(m)

        print(json.dumps({{
            "appels": appels,
            "env_lu": "DB_HOST" in os.environ,
            "sys_path_modifie": sys.path != chemin_avant,
            "filtres_modifies": warnings.filters != filtres_avant,
        }}))
    """)

    assert _executer(code, tmp_path) == {
        "appels": [],
        "env_lu": False,
        "sys_path_modifie": False,
        "filtres_modifies": False,
    }


def test_commun_est_pur(tmp_path):
    """`commun` (et le paquet de haut niveau) n'importe ni la base ni le pipeline."""
    code = textwrap.dedent("""
        import json, sys
        import genealogie_acadienne
        from genealogie_acadienne.commun import comparer, Personne, trouver_noms_partages
        interdits = ["pandas", "pymysql", "dotenv",
                     "genealogie_acadienne.donnees", "genealogie_acadienne.pipeline"]
        print(json.dumps(sorted(m for m in interdits if m in sys.modules)))
    """)
    assert _executer(code, tmp_path) == []


def test_donnees_n_importe_pas_le_pipeline(tmp_path):
    code = textwrap.dedent("""
        import json, sys
        import genealogie_acadienne.donnees
        print(json.dumps("genealogie_acadienne.pipeline" in sys.modules))
    """)
    assert _executer(code, tmp_path) is False


def test_api_publique():
    import genealogie_acadienne as ga

    for nom in ga.__all__:
        assert hasattr(ga, nom), nom
    assert set(ga.__all__) <= set(dir(ga))
