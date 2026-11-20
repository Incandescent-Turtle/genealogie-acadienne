"""
Fonctions communes et PURES : modèle `Personne`, normalisation et regroupement
des noms, comparaison de deux personnes, critères concordants.

Aucune base de données, aucune entrée/sortie ; n'importe ni pandas ni pymysql
(`trouver_noms_partages` reçoit un DataFrame déjà construit).
"""

from .comparaison import RapportComplet, afficher_comparaison, comparer
from .gedcom import Evenement, evenements_gedcom
from .criteres import VERDICTS_POSITIFS, criteres_concordants
from .modele import Faits, Mariage, Personne, Proche
from .noms import chercher_meme_nom, normaliser, trouver_noms_partages

__all__ = [
    "Personne", "Mariage", "Proche", "Faits",
    "normaliser", "trouver_noms_partages", "chercher_meme_nom",
    "comparer", "afficher_comparaison", "RapportComplet",
    "criteres_concordants", "VERDICTS_POSITIFS",
    "evenements_gedcom", "Evenement",
]
