"""
Convertir un dump MariaDB/MySQL (`.sql`) en fichiers Parquet, une table par fichier.

    genealogie-export-sql chemin/dump.sql chemin/parquet/

Étapes :
  1. trouver MariaDB, ou télécharger la version portable officielle une fois
     (dans `.mariadb/` à côté du dump, sauf `--cache`) ;
  2. démarrer un serveur temporaire et privé, y importer le dump ;
  3. exporter les tables généalogiques en Parquet + `manifeste.json`
     (jamais les tables d'utilisateurs ou de sessions, voir `donnees/export_parquet.py`) ;
  4. arrêter le serveur et supprimer la base temporaire (sauf `--garder-base`).

Le dump n'est jamais modifié.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ..donnees.db import get_connection
from ..donnees.export_parquet import exporter_base
from ..donnees.mariadb_local import importer_dump, obtenir_mariadb, serveur_temporaire, somme_sha256


def lire_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="genealogie-export-sql", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dump", type=Path, help="fichier .sql (dump MariaDB/MySQL)")
    p.add_argument("sortie", type=Path, help="dossier des fichiers Parquet")
    p.add_argument("--tables", nargs="+", metavar="TABLE",
                   help="exporter exactement ces tables (remplace le choix par défaut)")
    p.add_argument("--exclure", nargs="+", default=[], metavar="TABLE", help="tables à ne pas exporter")
    p.add_argument("--mariadb", type=Path, metavar="DOSSIER",
                   help="dossier d'une installation MariaDB (sinon PATH, sinon version portable)")
    p.add_argument("--cache", type=Path, metavar="DOSSIER",
                   help="où garder MariaDB et la base temporaire (défaut : .mariadb/ à côté du dump)")
    p.add_argument("--garder-base", action="store_true", help="ne pas supprimer la base temporaire")
    p.add_argument("--ecraser", action="store_true", help="remplacer un export existant dans la sortie")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = lire_arguments(argv)
    dump: Path = args.dump.resolve()
    if not dump.is_file():
        sys.exit(f"Dump introuvable : {dump}")
    cache = (args.cache or dump.parent / ".mariadb").resolve()

    debut = time.monotonic()
    mariadb = obtenir_mariadb(cache, args.mariadb)
    print(f"MariaDB : {mariadb.serveur}", file=sys.stderr)
    source = {"fichier": dump.name, "octets": dump.stat().st_size, "sha256": somme_sha256(dump)}

    with serveur_temporaire(mariadb, cache, garder=args.garder_base) as config:
        importer_dump(mariadb, config, dump)
        print(f"Exportation vers {args.sortie}", file=sys.stderr)
        conn = get_connection(config)
        try:
            manifeste = exporter_base(conn, args.sortie, tables=args.tables, exclure=args.exclure,
                                      source=source, ecraser=args.ecraser)
        finally:
            conn.close()

    n = len(manifeste["tables"])
    print(f"Terminé en {time.monotonic() - debut:.0f} s : {n} tables dans {args.sortie} "
          f"(non exportées : {', '.join(manifeste['tables_non_exportees']) or 'aucune'})", file=sys.stderr)


if __name__ == "__main__":
    main()
