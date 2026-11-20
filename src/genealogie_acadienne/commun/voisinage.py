"""
Liens familiaux typés et voisinage à k sauts, à partir de `Personne`.

Depuis `genealogie_acadienne` 93a34cf, chaque `Proche` porte le `person_id`
du proche (même arbre). On peut donc reconstruire le graphe familial :

  (tree_id, parent)  --parent_de-->  (tree_id, enfant)
  (tree_id, enfant)  --enfant_de-->  (tree_id, parent)
  (tree_id, a)       --conjoint_de-> (tree_id, b)      (dans les deux sens)

Les liens ne traversent jamais les arbres (un xref n'a de sens que dans son
arbre). Un proche absent de l'index (non chargé) est ignoré par le voisinage
mais reste visible dans `Personne.parents` etc. Module pur : aucune base.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping

from .modele import Personne

Cle = tuple[int, str]  # (tree_id, person_id)

RELATIONS = ("parent_de", "enfant_de", "conjoint_de")


def cle(p: Personne) -> Cle:
    """La clé d'une personne : (tree_id, person_id)."""
    return int(p.tree_id), str(p.person_id)


def indexer(personnes: Iterable[Personne]) -> dict[Cle, Personne]:
    """{(tree_id, person_id): Personne}."""
    return {cle(p): p for p in personnes}


def liens_de(p: Personne) -> list[tuple[str, Cle]]:
    """Les liens sortants d'une personne : [(relation, clé du proche), ...].

    Les proches sans `person_id` (dictionnaires construits à la main) sont ignorés.
    """
    arbre = int(p.tree_id)
    liens: list[tuple[str, Cle]] = []
    vus: set[tuple[str, Cle]] = set()

    def ajouter(relation: str, proche_id: str | None) -> None:
        if proche_id:
            lien = (relation, (arbre, str(proche_id)))
            if lien not in vus:
                vus.add(lien)
                liens.append(lien)

    for parent in p.parents:
        ajouter("enfant_de", parent.get("person_id"))
    for enfant in p.enfants:
        ajouter("parent_de", enfant.get("person_id"))
    for conjoint in p.conjoints:
        ajouter("conjoint_de", conjoint.get("person_id"))
    for mariage in p.mariages:
        ajouter("conjoint_de", mariage.get("conjoint_id"))
    return liens


def tous_les_liens(index: Mapping[Cle, Personne]) -> list[tuple[Cle, str, Cle]]:
    """Tous les liens (source, relation, destination) entre personnes de l'index.

    Chaque lien est rendu symétrique : si A --enfant_de--> B est connu par A
    seulement, on ajoute aussi B --parent_de--> A. Ordre déterministe.
    """
    inverse = {"parent_de": "enfant_de", "enfant_de": "parent_de", "conjoint_de": "conjoint_de"}
    liens: set[tuple[Cle, str, Cle]] = set()
    for source, p in index.items():
        for relation, destination in liens_de(p):
            if destination in index and destination != source:
                liens.add((source, relation, destination))
                liens.add((destination, inverse[relation], source))
    return sorted(liens)


def voisinage(
    depart: Cle, index: Mapping[Cle, Personne], k: int,
    adjacence: Mapping[Cle, list[tuple[str, Cle]]] | None = None,
) -> dict[Cle, int]:
    """Les personnes à au plus `k` sauts de `depart` : {clé: distance}.

    `adjacence` (voir `adjacence`) évite de recalculer les liens pour
    plusieurs départs. Le départ est inclus (distance 0).
    """
    if depart not in index:
        return {}
    if adjacence is None:
        adjacence = construire_adjacence(index)
    distances = {depart: 0}
    file = deque([depart])
    while file:
        courant = file.popleft()
        if distances[courant] >= k:
            continue
        for _, voisin in adjacence.get(courant, []):
            if voisin not in distances:
                distances[voisin] = distances[courant] + 1
                file.append(voisin)
    return distances


def construire_adjacence(index: Mapping[Cle, Personne]) -> dict[Cle, list[tuple[str, Cle]]]:
    """{clé: [(relation, voisin), ...]} pour tous les liens symétrisés de l'index."""
    adjacence: dict[Cle, list[tuple[str, Cle]]] = {c: [] for c in index}
    for source, relation, destination in tous_les_liens(index):
        adjacence[source].append((relation, destination))
    return adjacence


def proches_par_role(p: Personne, index: Mapping[Cle, Personne]) -> dict[str, list[Personne]]:
    """Les proches d'une personne présents dans l'index, par rôle :
    {"pere", "mere", "parents_inconnus", "conjoints", "enfants"}."""
    roles: dict[str, list[Personne]] = {"pere": [], "mere": [], "parents_inconnus": [],
                                        "conjoints": [], "enfants": []}
    for relation, c in liens_de(p):
        q = index.get(c)
        if q is None:
            continue
        if relation == "enfant_de":
            role = {"M": "pere", "F": "mere"}.get(q.sexe, "parents_inconnus")
            roles[role].append(q)
        elif relation == "parent_de":
            roles["enfants"].append(q)
        elif q not in roles["conjoints"]:
            roles["conjoints"].append(q)
    return roles
