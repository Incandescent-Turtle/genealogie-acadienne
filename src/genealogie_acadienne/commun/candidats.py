"""
Génération de candidats par nom « relâché » (blocage).

Pour une personne, les candidats sont les personnes qui partagent :
  - une CLÉ DE NOM DE FAMILLE (`variantes.cles_noms_famille` : variantes
    orthographiques et alias « dit » compris), ET
  - au moins UN PRÉNOM CANONIQUE (`variantes.cles_prenoms` : Marie / Mary,
    prénom principal omis, alias « dit » compris).

C'est volontairement large : « Marie Louise Comeaux » trouve « Louise Comeau »,
« Mary Comeaux » et « Louise Comeaux dite Rose ». Ça généralise
`genealogie_acadienne.trouver_paires` (partage1) aux variantes de noms.

Les noms alternatifs (`Personne.noms_alternatifs`) sont aussi indexés.
Module pur : aucune base.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .modele import Personne

from .variantes import cles_noms_famille, cles_prenoms, nom_famille_probable
from .voisinage import Cle, cle


def cles_blocage(p: Personne) -> frozenset[tuple[str, str]]:
    """Les clés (nom de famille, prénom) d'une personne, tous noms confondus."""
    cles: set[tuple[str, str]] = set()
    for nom in [p.nom_complet, *p.noms_alternatifs]:
        famille = p.nom_famille if nom == p.nom_complet else ""
        famille = nom_famille_probable(nom, famille)
        for nf in cles_noms_famille(famille, nom):
            for pr in cles_prenoms(nom, famille):
                cles.add((nf, pr))
    return frozenset(cles)


class IndexCandidats:
    """Index inversé (nom de famille, prénom) -> personnes, construit une fois."""

    def __init__(self, population: Iterable[Personne]):
        self.personnes: dict[Cle, Personne] = {}
        self._index: dict[tuple[str, str], set[Cle]] = defaultdict(set)
        for p in population:
            c = cle(p)
            self.personnes[c] = p
            for b in cles_blocage(p):
                self._index[b].add(c)

    def candidats(
        self,
        p: Personne,
        exclure_meme_arbre: bool = True,
        arbres_exclus: Iterable[int] = (),
        sexe_compatible: bool = True,
    ) -> list[Cle]:
        """Les candidats de `p` (sans `p` lui-même), triés par clé.

        `exclure_meme_arbre` : on ne propose pas les personnes du même arbre.
        `arbres_exclus` : arbres jamais proposés (ex. l'arbre des clones).
        `sexe_compatible` : on écarte les sexes connus et différents (M vs F).
        """
        moi = cle(p)
        exclus = {int(a) for a in arbres_exclus}
        trouves: set[Cle] = set()
        for b in cles_blocage(p):
            trouves |= self._index.get(b, set())
        resultat = []
        for c in trouves:
            if c == moi or c[0] in exclus:
                continue
            if exclure_meme_arbre and c[0] == moi[0]:
                continue
            q = self.personnes[c]
            if sexe_compatible and {p.sexe, q.sexe} == {"M", "F"}:
                continue
            resultat.append(c)
        return sorted(resultat)


def generer_candidats(
    requetes: Iterable[Personne], population: Iterable[Personne], **options
) -> dict[Cle, list[Cle]]:
    """{clé de la requête: [clés des candidats]} (options : voir `IndexCandidats.candidats`)."""
    index = IndexCandidats(population)
    return {cle(p): index.candidats(p, **options) for p in requetes}
