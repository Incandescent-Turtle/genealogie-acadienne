"""
Serveur MariaDB temporaire et privé, pour importer un dump `.sql` sans installation.

`serveur_temporaire(...)` :
  1. trouve MariaDB (dossier donné, sinon `mariadbd` dans le PATH, sinon
     télécharge une fois la version portable officielle, vérifiée par SHA-256) ;
  2. crée une base vide dans un dossier temporaire et démarre `mariadbd`,
     joignable seulement en local (127.0.0.1, port libre, compte à mot de passe aléatoire) ;
  3. donne un `DBConfig` pour s'y connecter ;
  4. à la sortie, arrête le serveur et supprime le dossier (sauf `garder=True`).

`importer_dump(...)` rejoue un dump avec le client officiel `mariadb`.

Versions portables : Linux x86_64 (.tar.gz) et Windows x64 (.zip). Ailleurs
(macOS...), installer MariaDB (`brew install mariadb`) ou passer son dossier.
"""

from __future__ import annotations

import hashlib
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pymysql

from .db import DBConfig, get_connection

VERSION_MARIADB = "10.11.20"
# Serveurs officiels, essayés dans l'ordre (archive.mariadb.org est très lent).
SERVEURS_TELECHARGEMENT = (
    f"https://dlm.mariadb.com/repo/mariadb-server/{VERSION_MARIADB}",
    f"https://archive.mariadb.org/mariadb-{VERSION_MARIADB}",
)
# (système, machine) -> (chemin sur les serveurs, sha256), sommes tirées de sha256sums.txt.
VERSIONS_PORTABLES: dict[tuple[str, str], tuple[str, str]] = {
    ("Linux", "x86_64"): (
        f"bintar-linux-systemd-x86_64/mariadb-{VERSION_MARIADB}-linux-systemd-x86_64.tar.gz",
        "3e28539f79de3ca9df72f4a4b93f9092eb4f05a9648391ddf37c44fb4ed84727",
    ),
    ("Windows", "AMD64"): (
        f"winx64-packages/mariadb-{VERSION_MARIADB}-winx64.zip",
        "aad30008fd9ce30c12366edc6414920d8596e69d7db94de50c63642a6e2982c3",
    ),
}
BASE_IMPORT = "importation"
UTILISATEUR = "export"
ACCES_REFUSE = 1045
EXE = ".exe" if os.name == "nt" else ""


@dataclass(frozen=True)
class InstallationMariaDB:
    """Chemins des trois programmes utilisés."""
    basedir: Path
    serveur: Path        # mariadbd
    installation: Path   # mariadb-install-db
    client: Path         # mariadb


def _chercher(basedir: Path, nom: str) -> Path | None:
    for sous in ("bin", "sbin", "scripts"):
        p = basedir / sous / f"{nom}{EXE}"
        if p.is_file():
            return p
    return None


def installation_depuis(basedir: str | Path) -> InstallationMariaDB:
    """Décrit une installation MariaDB à partir de son dossier racine."""
    basedir = Path(basedir).resolve()
    serveur, installation, client = (_chercher(basedir, n) for n in ("mariadbd", "mariadb-install-db", "mariadb"))
    if serveur is None or installation is None or client is None:
        raise FileNotFoundError(
            f"MariaDB incomplet dans {basedir} : il faut mariadbd, mariadb-install-db et mariadb.")
    return InstallationMariaDB(basedir, serveur, installation, client)


def version_portable(systeme: str | None = None, machine: str | None = None) -> tuple[list[str], str] | None:
    """(urls, sha256) de la version portable pour cette plateforme, ou None."""
    cle = (systeme or platform.system(), machine or platform.machine())
    if cle not in VERSIONS_PORTABLES:
        return None
    chemin, sha256 = VERSIONS_PORTABLES[cle]
    return [f"{serveur}/{chemin}" for serveur in SERVEURS_TELECHARGEMENT], sha256


def somme_sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _telecharger(urls: list[str], sha256: str, destination: Path) -> None:
    """Télécharge depuis le premier serveur qui répond, avec vérification SHA-256."""
    partiel = destination.with_name(destination.name + ".partiel")
    erreurs = []
    for url in urls:
        print(f"Téléchargement de MariaDB {VERSION_MARIADB} (une seule fois) : {url}", file=sys.stderr)
        try:
            with urllib.request.urlopen(url, timeout=60) as rep, open(partiel, "wb") as f:
                total = int(rep.headers.get("Content-Length") or 0)
                lu = 0
                while bloc := rep.read(1 << 20):
                    f.write(bloc)
                    lu += len(bloc)
                    if total:
                        print(f"\r  {lu / 1e6:.0f} / {total / 1e6:.0f} Mo", end="", file=sys.stderr)
            print(file=sys.stderr)
            if somme_sha256(partiel) != sha256:
                raise RuntimeError("somme SHA-256 incorrecte")
        except (OSError, RuntimeError) as e:
            print(f"\n  échec : {e}", file=sys.stderr)
            erreurs.append(f"{url} : {e}")
            partiel.unlink(missing_ok=True)
            continue
        partiel.replace(destination)
        return
    raise RuntimeError("Téléchargement de MariaDB impossible :\n" + "\n".join(erreurs))


def obtenir_mariadb(cache: str | Path, basedir: str | Path | None = None) -> InstallationMariaDB:
    """Trouve MariaDB : `basedir`, sinon le PATH, sinon la version portable dans `cache`."""
    if basedir is not None:
        return installation_depuis(basedir)

    dans_path = shutil.which("mariadbd")
    if dans_path is None and os.name != "nt":  # /usr/sbin n'est pas toujours dans le PATH
        dans_path = shutil.which("mariadbd", path="/usr/sbin:/usr/local/sbin")
    if dans_path:
        return installation_depuis(Path(dans_path).resolve().parent.parent)

    version = version_portable()
    if version is None:
        raise RuntimeError(
            f"Pas de MariaDB portable pour {platform.system()} {platform.machine()}. "
            "Installez MariaDB (ex. `brew install mariadb`) ou passez son dossier."
        )
    urls, sha256 = version
    cache = Path(cache)
    archive = cache / urls[0].rsplit("/", 1)[1]
    dossier = cache / archive.name.removesuffix(".tar.gz").removesuffix(".zip")
    if not dossier.is_dir():
        cache.mkdir(parents=True, exist_ok=True)
        if not archive.is_file():
            _telecharger(urls, sha256, archive)
        print(f"Extraction dans {dossier}...", file=sys.stderr)
        temporaire = Path(tempfile.mkdtemp(prefix="extraction-", dir=cache))
        try:
            if archive.suffix == ".zip":
                with zipfile.ZipFile(archive) as z:
                    z.extractall(temporaire)
            else:
                with tarfile.open(archive) as tar:
                    tar.extractall(temporaire, filter="data")
            (temporaire / dossier.name).replace(dossier)
        finally:
            shutil.rmtree(temporaire, ignore_errors=True)
        archive.unlink()  # l'archive ne sert plus une fois extraite
    return installation_depuis(dossier)


def _port_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _attendre(config: DBConfig, processus: subprocess.Popen, journal: Path, delai: float = 120) -> None:
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if processus.poll() is not None:
            raise RuntimeError(f"mariadbd s'est arrêté au démarrage. Journal :\n{_fin_journal(journal)}")
        try:
            get_connection(config).close()
            return
        except pymysql.err.OperationalError as e:
            if e.args and e.args[0] == ACCES_REFUSE:  # le serveur répond : inutile d'attendre
                raise RuntimeError(f"mariadbd refuse la connexion : {e}") from None
            time.sleep(0.5)
    raise RuntimeError(f"mariadbd ne répond pas après {delai:.0f} s. Journal :\n{_fin_journal(journal)}")


def _fin_journal(journal: Path, n: int = 20) -> str:
    try:
        return "\n".join(journal.read_text(errors="replace").splitlines()[-n:])
    except OSError:
        return "(pas de journal)"


@contextmanager
def serveur_temporaire(
    mariadb: InstallationMariaDB,
    dossier_parent: str | Path,
    garder: bool = False,
    memoire_innodb: str = "256M",
) -> Iterator[DBConfig]:
    """Démarre un `mariadbd` jetable et donne un `DBConfig` vers sa base vide `importation`."""
    dossier_parent = Path(dossier_parent)
    dossier_parent.mkdir(parents=True, exist_ok=True)
    racine = Path(tempfile.mkdtemp(prefix="base-", dir=dossier_parent))
    donnees, journal = racine / "donnees", racine / "erreurs.log"
    mot_de_passe = secrets.token_urlsafe(24)
    port = _port_libre()

    installer = [str(mariadb.installation)]
    if os.name != "nt":
        installer += ["--no-defaults", f"--basedir={mariadb.basedir}",
                      "--auth-root-authentication-method=normal", "--skip-test-db"]
    installer.append(f"--datadir={donnees}")
    subprocess.run(installer, check=True, capture_output=True)

    # Exécuté par le serveur au démarrage : un compte local avec un mot de passe aléatoire.
    init = racine / "init.sql"
    init.write_text(f"CREATE USER '{UTILISATEUR}'@'127.0.0.1' IDENTIFIED BY '{mot_de_passe}';\n"
                    f"GRANT ALL PRIVILEGES ON *.* TO '{UTILISATEUR}'@'127.0.0.1';\n"
                    f"CREATE DATABASE `{BASE_IMPORT}` CHARACTER SET utf8mb4;\n")

    # Socket Unix court dans le dossier temporaire du système (limite de ~100 caractères).
    prise = Path(tempfile.gettempdir()) / f"mariadb-{secrets.token_hex(4)}.sock"
    commande = [str(mariadb.serveur)]
    if os.name != "nt":
        commande += ["--no-defaults", f"--socket={prise}"]
    commande += [
        f"--basedir={mariadb.basedir}", f"--datadir={donnees}",
        f"--port={port}", "--bind-address=127.0.0.1", "--skip-name-resolve",
        f"--init-file={init}", f"--log-error={journal}", f"--pid-file={racine / 'mariadbd.pid'}",
        "--character-set-server=utf8mb4", "--skip-log-bin", "--max-allowed-packet=1G",
        f"--innodb-buffer-pool-size={memoire_innodb}", "--innodb-log-file-size=256M",
        "--innodb-flush-log-at-trx-commit=0", "--innodb-doublewrite=0",
    ]
    processus = subprocess.Popen(commande, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    config = DBConfig(host="127.0.0.1", user=UTILISATEUR, password=mot_de_passe,
                      database=BASE_IMPORT, port=port)
    try:
        _attendre(config, processus, journal)
        yield config
    finally:
        _arreter(config, processus)
        init.unlink(missing_ok=True)  # contient le mot de passe
        if garder:
            print(f"Base gardée dans {racine}", file=sys.stderr)
        else:
            shutil.rmtree(racine, ignore_errors=True)


def _arreter(config: DBConfig, processus: subprocess.Popen) -> None:
    if processus.poll() is not None:
        return
    try:
        conn = get_connection(config)
        with conn.cursor() as cur:
            cur.execute("SHUTDOWN")
        conn.close()
    except pymysql.err.Error:
        processus.terminate()
    try:
        processus.wait(timeout=120)
    except subprocess.TimeoutExpired:
        processus.kill()
        processus.wait()


def importer_dump(mariadb: InstallationMariaDB, config: DBConfig, dump: str | Path) -> None:
    """Rejoue `dump` dans la base de `config` avec le client `mariadb` (progression affichée)."""
    dump = Path(dump)
    total = dump.stat().st_size
    commande = [str(mariadb.client), "--no-defaults", f"--host={config.host}", f"--port={config.port}",
                f"--user={config.user}", "--default-character-set=utf8mb4",
                "--max-allowed-packet=1G", config.database]
    env = {**os.environ, "MYSQL_PWD": config.password}
    with open(dump, "rb") as f, subprocess.Popen(commande, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                                                 stdout=subprocess.DEVNULL, env=env) as proc:
        assert proc.stdin is not None and proc.stderr is not None
        envoye = 0
        try:
            while bloc := f.read(1 << 20):
                proc.stdin.write(bloc)
                envoye += len(bloc)
                print(f"\rImportation : {100 * envoye / total:.0f} %", end="", file=sys.stderr)
        except BrokenPipeError:
            pass  # le client s'est arrêté : l'erreur est lue plus bas
        finally:
            print(file=sys.stderr)
            proc.stdin.close()
        erreurs = proc.stderr.read().decode(errors="replace")
        if proc.wait() != 0:
            raise RuntimeError(f"Échec de l'importation de {dump} :\n{erreurs}")
