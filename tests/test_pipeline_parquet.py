"""Les scripts de `pipeline` sur un export Parquet (mini-base, aucune vraie base).

Chaque requête est exécutée sur la copie SQLite : une syntaxe propre à MariaDB
ferait échouer le test."""

from __future__ import annotations

import fausse_base
import pandas as pd
import pytest

from genealogie_acadienne.donnees import (
    connexion_parquet,
    ouvrir_connexion,
    source_parquet,
)
from genealogie_acadienne.pipeline import (
    apparier_personnes,
    comparer_paire,
    statistiques,
    trouver_erreurs,
)


@pytest.fixture
def export(tmp_path):
    base = fausse_base.creer()
    fausse_base.exporter(base, tmp_path / "export", copies=(2,))  # arbre 2 = copie de l'arbre 1
    base.close()
    return tmp_path / "export"


@pytest.fixture
def conn(export):
    c = connexion_parquet(export)
    yield c
    c.close()


@pytest.mark.parametrize("critere", statistiques.CRITERES, ids=lambda m: m["nom"])
def test_statistiques(conn, critere):
    df = critere["fn"](conn)
    assert list(df.columns) == ["tree_id", "person_id", "sexe", "valeur"]


def test_statistiques_valeurs(conn):
    vie = statistiques.duree_vie(conn).set_index(["tree_id", "person_id"])["valeur"]
    assert float(vie.loc[(1, "I5")]) == pytest.approx(60, abs=0.01)          # 1730 -> 1790
    enfants = statistiques.nombre_enfants(conn).set_index(["tree_id", "person_id"])["valeur"]
    assert int(enfants.loc[(1, "I1")]) == 2 and int(enfants.loc[(1, "I3")]) == 1


@pytest.mark.parametrize("fn", [
    trouver_erreurs.lieux_ressemblant_a_des_dates, trouver_erreurs.lieux_avec_chiffres,
    trouver_erreurs.annees_impossibles, trouver_erreurs.naissance_apres_deces,
    trouver_erreurs.age_au_deces_improbable, trouver_erreurs.noms_avec_chiffres,
], ids=lambda f: f.__name__)
def test_trouver_erreurs(conn, fn):
    assert list(fn(conn).columns) == trouver_erreurs.COLONNES


def test_regexp(conn):
    df = trouver_erreurs.lieux_ressemblant_a_des_dates(conn)
    assert set(df["valeur"]) == {"Grand-Pré 1755"}                # REGEXP fourni par Python
    assert trouver_erreurs.lieux_avec_chiffres(conn).empty        # NOT REGEXP


def test_mains_lisent_l_export(export, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "rapports").mkdir()
    statistiques.main(["--parquet", str(export)])
    assert "Durée de vie" in (tmp_path / "rapports" / "statistiques.md").read_text(encoding="utf-8")
    trouver_erreurs.main(["--parquet", str(export)])
    assert "Grand-Pré 1755" in (tmp_path / "erreurs_a_corriger.txt").read_text(encoding="utf-8")


def test_comparer_paire(conn):
    a, b, rapport = comparer_paire.comparer_ids(conn, 1, "I3", 2, "I3")
    assert a.nom_complet == b.nom_complet == "Pierre Babin"
    assert rapport["naissance"]["verdict"]


def test_apparier_vers_parquet(export, tmp_path):
    avant = sorted(p.name for p in export.iterdir())
    sortie = tmp_path / "paires.parquet"
    apparier_personnes.main(["--parquet", str(export), "--sortie", str(sortie)])

    paires = pd.read_parquet(sortie)
    assert len(paires) > 0
    assert set(paires["tree_id_a"]) == {1} and set(paires["tree_id_b"]) == {2}
    assert bool((paires["person_id_a"] == paires["person_id_b"]).all())  # copies : même personne
    assert list(paires.columns) == apparier_personnes.COLONNES + ["comparison_date"]
    assert sorted(p.name for p in export.iterdir()) == avant       # export inchangé


def test_apparier_parquet_sans_sortie(export):
    with pytest.raises(SystemExit):
        apparier_personnes.main(["--parquet", str(export)])


def test_sans_parquet_on_ouvre_mariadb(monkeypatch):
    monkeypatch.setattr(source_parquet, "load_env_file", lambda **kw: False)
    class FausseMariaDB:
        ferme = False

        def close(self):
            self.ferme = True

    base = FausseMariaDB()
    monkeypatch.setattr(source_parquet, "get_connection", lambda: base)
    with ouvrir_connexion() as conn:
        assert conn is base and not base.ferme
    assert base.ferme
