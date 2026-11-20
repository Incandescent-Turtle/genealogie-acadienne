"""
Fonctions communes et PURES : modèle `Personne`, normalisation et regroupement
des noms, variantes de noms, candidats, dates GEDCOM, liens familiaux et
voisinage, clonage, population synthétique, comparaison de deux personnes,
critères concordants.

Aucune base de données, aucune entrée/sortie ; n'importe ni pandas ni pymysql
(`trouver_noms_partages` reçoit un DataFrame déjà construit).
"""

from .comparaison import RapportComplet, afficher_comparaison, comparer
from .gedcom import Evenement, evenements_gedcom
from .candidats import IndexCandidats, cles_blocage, generer_candidats
from .clonage import choisir_bien_documentees, cloner_famille, score_documentation, taille_famille
from .dates import DateGedcom, analyser_date, decaler_date, ecart_annees
from .synthetique import PopulationSynthetique, generer_population
from .variantes import cle_nom_famille, cle_prenom, cles_noms_famille, cles_prenoms
from .voisinage import construire_adjacence, indexer, liens_de, proches_par_role, tous_les_liens, voisinage
from .criteres import VERDICTS_POSITIFS, criteres_concordants
from .modele import Faits, Mariage, Personne, Proche
from .noms import (
    alias_dit,
    chercher_meme_nom,
    normaliser,
    tokens_prenoms,
    trouver_noms_partages,
    trouver_paires,
)

__all__ = [
    "Personne", "Mariage", "Proche", "Faits",
    "normaliser", "trouver_noms_partages", "chercher_meme_nom",
    "comparer", "afficher_comparaison", "RapportComplet",
    "criteres_concordants", "VERDICTS_POSITIFS",
    "evenements_gedcom", "Evenement",
    "alias_dit", "tokens_prenoms", "trouver_paires",
    "cle_prenom", "cle_nom_famille", "cles_prenoms", "cles_noms_famille",
    "IndexCandidats", "cles_blocage", "generer_candidats",
    "DateGedcom", "analyser_date", "decaler_date", "ecart_annees",
    "indexer", "liens_de", "tous_les_liens", "voisinage", "construire_adjacence", "proches_par_role",
    "score_documentation", "taille_famille", "choisir_bien_documentees", "cloner_famille",
    "PopulationSynthetique", "generer_population",
]
