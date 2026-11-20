"""
Instantanés Parquet : exporter des `Personne` une fois, puis travailler sans base.

Un instantané est un dossier :
  personnes.parquet  une ligne par personne (table des nœuds)
  liens.parquet      un lien typé par ligne (table des arêtes, voir `voisinage`)
  manifeste.json     source, date, nombre de personnes, version du paquet...

`personnes.parquet` est lisible tel quel : les faits sont aplatis en colonnes
(`annee_BIRT`, `date_BIRT`, `lieu_BIRT`, ...). Les listes (mariages, parents,
enfants, conjoints, noms alternatifs) sont en JSON, pour garder exactement les
`Mariage` / `Proche` chargés (y compris les proches absents de l'instantané).

`lire_instantane` reconstruit des `Personne` identiques à celles exportées.
Dépendances : pandas + pyarrow (pas de base, sauf `instantane_depuis_base`).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from ..commun.modele import Personne

from ..commun.voisinage import indexer, tous_les_liens

if TYPE_CHECKING:
    from pymysql.connections import Connection

FAITS = ("BIRT", "BAPM", "CHR", "DEAT", "BURI")
LISTES = ("noms_alternatifs", "mariages", "parents", "enfants", "conjoints")
SCALAIRES = ("tree_id", "person_id", "nom_complet", "nom_norm", "sexe", "prenoms", "nom_famille")

FICHIER_PERSONNES = "personnes.parquet"
FICHIER_LIENS = "liens.parquet"
FICHIER_MANIFESTE = "manifeste.json"


def personnes_en_table(personnes: Iterable[Personne]) -> pd.DataFrame:
    """Une ligne par personne (faits aplatis, listes en JSON)."""
    lignes = []
    for p in personnes:
        ligne: dict[str, Any] = {c: getattr(p, c) for c in SCALAIRES}
        ligne["tree_id"] = int(p.tree_id)
        ligne["person_id"] = str(p.person_id)
        for f in FAITS:
            ligne[f"annee_{f}"] = p.faits.get(f)
            ligne[f"date_{f}"] = p.dates.get(f)
            ligne[f"lieu_{f}"] = p.lieux.get(f)
        # faits hors FAITS, et faits présents sans année (None) : gardés en JSON
        autres = {f: v for f, v in p.faits.items() if f not in FAITS or v is None}
        ligne["autres_faits"] = json.dumps(autres, ensure_ascii=False) if autres else None
        for c in LISTES:
            ligne[c] = json.dumps(getattr(p, c), ensure_ascii=False)
        lignes.append(ligne)
    df = pd.DataFrame(lignes)
    if df.empty:
        return df
    for f in FAITS:
        df[f"annee_{f}"] = df[f"annee_{f}"].astype("Int64")
    return df.sort_values(["tree_id", "person_id"]).reset_index(drop=True)


def _ou_none(v: Any) -> Any:
    return None if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA else v


def table_en_personnes(df: pd.DataFrame) -> list[Personne]:
    """Inverse de `personnes_en_table`."""
    personnes = []
    for r in df.to_dict(orient="records"):
        faits = {f: int(r[f"annee_{f}"]) for f in FAITS if _ou_none(r.get(f"annee_{f}")) is not None}
        if _ou_none(r.get("autres_faits")):
            faits.update(json.loads(r["autres_faits"]))
        personnes.append(Personne(
            tree_id=int(r["tree_id"]),
            person_id=str(r["person_id"]),
            nom_complet=r["nom_complet"] or "",
            nom_norm=r["nom_norm"] or "",
            sexe=r["sexe"] or "U",
            faits=faits,
            prenoms=_ou_none(r.get("prenoms")) or "",
            nom_famille=_ou_none(r.get("nom_famille")) or "",
            dates={f: r[f"date_{f}"] for f in FAITS if _ou_none(r.get(f"date_{f}"))},
            lieux={f: r[f"lieu_{f}"] for f in FAITS if _ou_none(r.get(f"lieu_{f}"))},
            **{c: json.loads(r[c]) if _ou_none(r.get(c)) else [] for c in LISTES},
        ))
    return personnes


def liens_en_table(personnes: Iterable[Personne]) -> pd.DataFrame:
    """Table des arêtes : tree_id, source, relation, destination (liens symétrisés)."""
    liens = tous_les_liens(indexer(personnes))
    return pd.DataFrame(
        [(s[0], s[1], rel, d[1]) for s, rel, d in liens],
        columns=["tree_id", "source", "relation", "destination"],
    )


def _version_paquet() -> str | None:
    try:
        return version("genealogie-acadienne")
    except PackageNotFoundError:
        return None


def ecrire_instantane(
    personnes: Iterable[Personne], dossier: str | Path, source: str, **infos: Any
) -> Path:
    """Écrit un instantané dans `dossier` (créé au besoin). Renvoie le dossier.

    `source` décrit l'origine (« base webtrees », « synthétique graine=0 »...) ;
    `infos` est ajouté tel quel au manifeste.
    """
    personnes = list(personnes)
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    personnes_en_table(personnes).to_parquet(dossier / FICHIER_PERSONNES, index=False)
    liens = liens_en_table(personnes)
    liens.to_parquet(dossier / FICHIER_LIENS, index=False)
    manifeste = {
        "source": source,
        "cree_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_personnes": len(personnes),
        "n_liens": len(liens),
        "n_arbres": len({p.tree_id for p in personnes}),
        "genealogie_acadienne": _version_paquet(),
        **infos,
    }
    (dossier / FICHIER_MANIFESTE).write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=2), encoding="utf-8")
    return dossier


def lire_instantane(dossier: str | Path) -> list[Personne]:
    """Relit les `Personne` d'un instantané."""
    return table_en_personnes(pd.read_parquet(Path(dossier) / FICHIER_PERSONNES))


def lire_manifeste(dossier: str | Path) -> dict[str, Any]:
    return json.loads((Path(dossier) / FICHIER_MANIFESTE).read_text(encoding="utf-8"))


def instantane_depuis_base(conn: Connection, dossier: str | Path) -> Path:
    """Charge TOUTES les personnes de la base (hors `ARBRES_IGNORES`) et les
    écrit dans un instantané. Lecture seule sur la base."""
    from .noms import charger_personnes
    from .personnes import charger_groupe

    noms = charger_personnes(conn)
    gens = noms[["tree_id", "person_id"]].drop_duplicates().itertuples(index=False)
    personnes = charger_groupe(conn, gens)
    return ecrire_instantane(personnes.values(), dossier, source="base webtrees")
