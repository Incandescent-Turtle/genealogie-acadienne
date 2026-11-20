from genealogie_acadienne.donnees import instantane
from genealogie_acadienne.commun.synthetique import generer_population


def _cle(p):
    return p.tree_id, p.person_id


def test_aller_retour(tmp_path, famille):
    famille[0].faits["DEAT"] = None              # fait présent sans année
    famille[0].faits["CENS"] = 1752              # fait hors liste
    famille[0].dates = {"BIRT": "ABT 3 MAR 1700"}
    famille[0].lieux = {"BIRT": "Port-Royal, Acadie"}
    famille[1].noms_alternatifs = ["Marie Babin"]
    dossier = instantane.ecrire_instantane(famille, tmp_path / "snap", source="test", graine=1)
    assert sorted(instantane.lire_instantane(dossier), key=_cle) == sorted(famille, key=_cle)
    manifeste = instantane.lire_manifeste(dossier)
    assert manifeste["n_personnes"] == 6 and manifeste["graine"] == 1
    # 6 liens parent-enfant et 2 unions, chacun dans les deux sens
    assert manifeste["n_liens"] == 2 * (6 + 2)


def test_aller_retour_synthetique(tmp_path):
    pop = generer_population(graine=3, n_fondateurs=4, n_generations=3, n_arbres=3)
    dossier = instantane.ecrire_instantane(pop.personnes, tmp_path, source="synthétique")
    assert sorted(instantane.lire_instantane(dossier), key=_cle) == sorted(pop.personnes, key=_cle)
