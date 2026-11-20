"""Garde-fous communs : aucun test ne doit toucher une vraie base."""

from __future__ import annotations

import socket

import pymysql
import pytest

from genealogie_acadienne import Personne, normaliser


class ConnexionInterdite(AssertionError):
    pass


@pytest.fixture(autouse=True)
def interdire_reseau(monkeypatch):
    """Toute tentative de connexion (pymysql ou socket) fait échouer le test."""
    def refuser(*args, **kwargs):
        raise ConnexionInterdite("Un test a essayé d'ouvrir une connexion.")

    monkeypatch.setattr(pymysql, "connect", refuser)
    monkeypatch.setattr(socket.socket, "connect", refuser)
    for var in ("DB_HOST", "DB_USER", "DB_PASS", "DB_NAME", "DB_PORT", "DB_PREFIX"):
        monkeypatch.delenv(var, raising=False)


def proche(nom: str, naissance: int | None = None) -> dict:
    return {"nom": nom, "nom_norm": normaliser(nom), "naissance": naissance}


def mariage(conjoint: str | None, annee: int | None = None) -> dict:
    return {"annee": annee, "conjoint": conjoint,
            "conjoint_norm": normaliser(conjoint) if conjoint else None}


def personne(nom: str = "Jean Babin", tree_id: int = 1, person_id: str = "I1",
             sexe: str = "M", **kwargs) -> Personne:
    """Construit une `Personne` à la main (aucune base)."""
    faits = kwargs.pop("faits", {})
    return Personne(tree_id=tree_id, person_id=person_id, nom_complet=nom,
                    nom_norm=normaliser(nom), sexe=sexe, faits=faits, **kwargs)
