"""Configuration de connexion injectable (sans vraie base)."""

from __future__ import annotations

import os

import pymysql
import pytest

from genealogie_acadienne.donnees import db


def test_config_depuis_env():
    cfg = db.DBConfig.from_env({"DB_HOST": "h", "DB_USER": "u", "DB_PASS": "secret",
                                "DB_NAME": "n", "DB_PORT": "3307"})
    assert cfg == db.DBConfig("h", "u", "secret", "n", 3307)
    assert "secret" not in repr(cfg)


def test_config_incomplete():
    with pytest.raises(ValueError):
        db.DBConfig.from_env({"DB_HOST": "h"})


def test_get_connection_utilise_la_config(monkeypatch):
    recu = {}
    monkeypatch.setattr(pymysql, "connect", lambda **kw: recu.update(kw) or "conn")

    conn = db.get_connection(db.DBConfig("h", "u", "p", "n", 3307))

    assert conn == "conn"
    assert recu == {"host": "h", "user": "u", "password": "p", "database": "n",
                    "port": 3307, "charset": "utf8mb4"}


def test_get_connection_lit_l_environnement(monkeypatch):
    recu = {}
    monkeypatch.setattr(pymysql, "connect", lambda **kw: recu.update(kw) or "conn")
    for k, v in {"DB_HOST": "h", "DB_USER": "u", "DB_PASS": "p", "DB_NAME": "n"}.items():
        monkeypatch.setenv(k, v)

    db.get_connection()

    assert recu["host"] == "h" and recu["port"] == 3306


def test_load_env_file(tmp_path, monkeypatch):
    fichier = tmp_path / ".env"
    fichier.write_text('DB_HOST="depuis_env"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DB_HOST", "avant")  # restauré par monkeypatch après le test

    assert db.load_env_file() is True
    assert os.environ["DB_HOST"] == "avant"  # par défaut, l'environnement gagne
    db.load_env_file(override=True)
    assert os.environ["DB_HOST"] == "depuis_env"


def test_prefixe_des_tables(monkeypatch):
    assert db.t("individuals") == "wt_individuals"
    monkeypatch.setenv("DB_PREFIX", "abc_")
    assert db.t("individuals") == "abc_individuals"
    db.set_table_prefix("x_")
    try:
        assert db.t("name") == "x_name"
    finally:
        db.set_table_prefix(None)
