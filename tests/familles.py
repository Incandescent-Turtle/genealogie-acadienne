"""Familles construites à la main, reliées par `person_id` (aucune base)."""

from genealogie_acadienne import Personne, normaliser


def proche(p: Personne) -> dict:
    return {"nom": p.nom_complet, "nom_norm": p.nom_norm,
            "naissance": p.faits.get("BIRT"), "person_id": p.person_id}


def personne(xref, nom, sexe, naissance=None, tree_id=1, nom_famille="", **kw) -> Personne:
    return Personne(tree_id=tree_id, person_id=xref, nom_complet=nom, nom_norm=normaliser(nom),
                    sexe=sexe, faits={"BIRT": naissance} if naissance else {},
                    nom_famille=nom_famille, **kw)


def relier(pere, mere, enfants):
    for p in (pere, mere):
        p.enfants = [proche(e) for e in enfants]
    pere.conjoints, mere.conjoints = [proche(mere)], [proche(pere)]
    pere.mariages = [{"annee": 1725, "conjoint": mere.nom_complet, "conjoint_norm": mere.nom_norm,
                      "conjoint_id": mere.person_id}]
    for e in enfants:
        e.parents = [proche(pere), proche(mere)]
