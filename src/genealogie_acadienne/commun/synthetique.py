"""
Population acadienne SYNTHÉTIQUE, sous forme de `Personne` en mémoire.

Sert au développement et aux tests (aucune donnée réelle) : elle passe par le
même pipeline qu'un instantané de la base.

Deux étapes :
  1. un MONDE « vrai » : des couples fondateurs (vers 1640-1680), puis
     plusieurs générations (mariages entre familles, enfants, décès), avec des
     prénoms et noms acadiens, des alias « dit » et des lieux ;
  2. plusieurs ARBRES qui recouvrent ce monde en partie (descendants d'un
     couple fondateur + conjoints + beaux-parents) ; une même vraie personne
     apparaît donc dans plusieurs arbres. Chaque arbre a son propre « bruit » :
     champs manquants, orthographe des noms, prénom principal omis, alias
     « dit », dates approximatives ou fausses d'un an ou deux, prénoms anglicisés.

`generer_population` renvoie aussi `identites` : {(tree_id, person_id): id vrai},
la vérité terrain des doublons naturels entre arbres.

Tout est déterministe pour une `graine` donnée. Module pur : aucune base.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .modele import Personne
from .noms import normaliser

from .dates import MOIS_GEDCOM

# --- Réservoirs de noms ----------------------------------------------------

NOMS_FAMILLE: dict[str, list[str]] = {
    # nom de famille: alias « dit » possibles
    "Babin": [], "Boudreau": [], "Comeau": [], "LeBlanc": ["Jasmin"],
    "Thibodeau": [], "Doucet": ["Laverdure"], "Gaudet": [], "Landry": [],
    "Richard": ["Sansoucy"], "Robichaud": [], "Hébert": ["Manuel"],
    "Arsenault": [], "Cormier": [], "Bourgeois": [], "Melanson": ["La Verdure"],
    "Poirier": [], "Savoie": [], "Thériault": [], "Aucoin": [], "Bourque": [],
    "Cyr": [], "Daigle": [], "Dugas": [], "Gautreau": [], "Girouard": ["Sainte-Croix"],
    "Granger": [], "Léger": ["La Rosette"], "Martin": ["Barnabé"], "Pitre": [],
    "Saulnier": [], "Trahan": [], "Belliveau": [], "Dupuis": [], "Gallant": [],
    "Petitpas": [], "Amirault": [], "Mius": ["d'Entremont"], "Bourg": ["Belle-Humeur"],
    "Vincent": ["Clément"], "Lord": ["La Montagne"],
}

VARIANTES_NOMS_FAMILLE: dict[str, list[str]] = {
    "Comeau": ["Comeaux", "Commeau"], "Thibodeau": ["Thibodeaux", "Thibaudeau"],
    "Boudreau": ["Boudreaux", "Boudrot"], "Arsenault": ["Arseneau", "Arsenaux"],
    "Doucet": ["Doucette"], "Melanson": ["Melançon"], "Thériault": ["Theriot", "Terriot"],
    "Robichaud": ["Robichaux"], "Gaudet": ["Gaudette"], "Savoie": ["Savoy"],
    "Hébert": ["Hebert", "Ébert"], "Landry": ["Landrie"], "LeBlanc": ["Leblanc", "Le Blanc"],
    "Gautreau": ["Gautreaux", "Gautrot"], "Léger": ["Leger", "Légère"],
    "Belliveau": ["Béliveau"], "Daigle": ["Daigre"], "Bourque": ["Bourk"],
}

PRENOMS_F = ["Marie", "Anne", "Marguerite", "Madeleine", "Catherine", "Élisabeth",
             "Cécile", "Françoise", "Jeanne", "Geneviève", "Louise", "Rosalie", "Agnès",
             "Hélène", "Isabelle", "Josephte", "Félicité", "Euphrosine", "Modeste",
             "Osite", "Brigitte", "Claire", "Judith"]
PRENOMS_M = ["Jean", "Pierre", "Joseph", "Charles", "François", "Jacques", "Michel",
             "Paul", "Claude", "Antoine", "Germain", "Olivier", "Étienne", "Alexis",
             "Simon", "Basile", "Honoré", "Amand", "Augustin", "Abraham", "Zacharie",
             "Isidore", "Louis", "Guillaume", "Baptiste", "Firmin"]

LIEUX = ["Port-Royal, Acadie", "Grand-Pré, Acadie", "Beaubassin, Acadie",
         "Pisiguit, Acadie", "Cobequid, Acadie", "Rivière-aux-Canards, Acadie",
         "Saint-Charles-des-Mines, Grand-Pré", "Annapolis Royal, Nouvelle-Écosse",
         "Louisbourg, Île Royale", "Memramcook, Nouveau-Brunswick",
         "Pubnico, Nouvelle-Écosse", "Chéticamp, Nouvelle-Écosse",
         "Caraquet, Nouveau-Brunswick", "Bouctouche, Nouveau-Brunswick",
         "Baie Sainte-Marie, Nouvelle-Écosse", "Saint-Basile, Madawaska"]

# prénom français (normalisé) -> forme anglaise, pour les arbres « anglicisés »
ANGLAIS = {
    "marie": "Mary", "jean": "John", "joseph": "Joseph", "pierre": "Peter", "jacques": "James",
    "francois": "Francis", "francoise": "Frances", "marguerite": "Margaret", "anne": "Ann",
    "elisabeth": "Elizabeth", "catherine": "Catherine", "madeleine": "Madeline",
    "charles": "Charles", "louis": "Lewis", "louise": "Louisa", "michel": "Michael",
    "guillaume": "William", "antoine": "Anthony", "etienne": "Stephen", "cecile": "Cecilia",
    "helene": "Helen", "jeanne": "Jane", "olivier": "Oliver", "augustin": "Austin",
    "zacharie": "Zachary", "isabelle": "Isabel", "rosalie": "Rosalie", "simon": "Simon",
}


# --- Le monde « vrai » -----------------------------------------------------

@dataclass
class DateVraie:
    annee: int
    mois: int
    jour: int


@dataclass
class Union:
    conjoint: int
    date: DateVraie | None
    lieu: str


@dataclass
class IndividuVrai:
    id: int
    sexe: str
    prenoms: list[str]
    nom_famille: str
    dit: str | None
    naissance: DateVraie
    lieu_naissance: str
    deces: DateVraie | None = None
    lieu_deces: str | None = None
    pere: int | None = None
    mere: int | None = None
    unions: list[Union] = field(default_factory=list)
    enfants: list[int] = field(default_factory=list)
    generation: int = 0


class _Monde:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.gens: dict[int, IndividuVrai] = {}

    def _date(self, annee: int) -> DateVraie:
        return DateVraie(annee, self.rng.randint(1, 12), self.rng.randint(1, 28))

    def _prenoms(self, sexe: str) -> list[str]:
        r = self.rng
        reservoir = PRENOMS_F if sexe == "F" else PRENOMS_M
        n = r.choices([1, 2, 3], weights=[4, 5, 1])[0]
        prenoms = r.sample(reservoir, n)
        # « Marie » en premier prénom pour beaucoup de filles, « Jean » / « Joseph » pour des garçons
        if sexe == "F" and r.random() < 0.55:
            prenoms = ["Marie"] + [p for p in prenoms if p != "Marie"][: max(1, n - 1)]
        elif sexe == "M" and r.random() < 0.2:
            premier = r.choice(["Jean", "Joseph"])
            prenoms = [premier] + [p for p in prenoms if p != premier][: max(1, n - 1)]
        return prenoms

    def nouvel_individu(self, sexe: str, annee: int, nom: str, dit: str | None,
                        lieu: str, generation: int) -> IndividuVrai:
        r = self.rng
        i = IndividuVrai(id=len(self.gens) + 1, sexe=sexe, prenoms=self._prenoms(sexe),
                         nom_famille=nom, dit=dit, naissance=self._date(annee),
                         lieu_naissance=lieu, generation=generation)
        # durée de vie : quelques morts en bas âge, sinon 40-85 ans
        age = r.randint(0, 5) if r.random() < 0.12 else r.randint(40, 85)
        i.deces = self._date(annee + age)
        i.lieu_deces = lieu if r.random() < 0.7 else r.choice(LIEUX)
        self.gens[i.id] = i
        return i

    def fondateur(self, sexe: str, annee: int, generation: int = 0) -> IndividuVrai:
        nom = self.rng.choice(sorted(NOMS_FAMILLE))
        dits = NOMS_FAMILLE[nom]
        dit = self.rng.choice(dits) if dits and self.rng.random() < 0.5 else None
        return self.nouvel_individu(sexe, annee, nom, dit, self.rng.choice(LIEUX), generation)

    def marier(self, a: IndividuVrai, b: IndividuVrai) -> int:
        annee = max(a.naissance.annee, b.naissance.annee) + self.rng.randint(19, 27)
        lieu = a.lieu_naissance if self.rng.random() < 0.6 else b.lieu_naissance
        date = self._date(annee)
        a.unions.append(Union(b.id, date, lieu))
        b.unions.append(Union(a.id, date, lieu))
        return annee

    def enfants_du_couple(self, pere: IndividuVrai, mere: IndividuVrai, annee_mariage: int,
                          generation: int) -> list[IndividuVrai]:
        r = self.rng
        fin = min(mere.naissance.annee + 44, mere.deces.annee, pere.deces.annee + 1)
        enfants, annee = [], annee_mariage + r.randint(1, 2)
        lieu = next(u.lieu for u in pere.unions if u.conjoint == mere.id)
        while annee <= fin and len(enfants) < 10:
            e = self.nouvel_individu(r.choice("MF"), annee, pere.nom_famille, pere.dit,
                                     lieu, generation)
            e.pere, e.mere = pere.id, mere.id
            pere.enfants.append(e.id)
            mere.enfants.append(e.id)
            enfants.append(e)
            annee += r.randint(1, 4)
        return enfants


def _construire_monde(rng: random.Random, n_fondateurs: int, n_generations: int) -> _Monde:
    monde = _Monde(rng)
    couples = []
    for _ in range(n_fondateurs):
        annee = rng.randint(1640, 1680)
        h = monde.fondateur("M", annee)
        f = monde.fondateur("F", annee + rng.randint(-8, 2))
        couples.append((h, f, monde.marier(h, f)))
    generation = 0
    while couples and generation < n_generations:
        generation += 1
        nes = [e for h, f, a in couples for e in monde.enfants_du_couple(h, f, a, generation)]
        adultes = [e for e in nes if e.deces.annee - e.naissance.annee >= 18]
        rng.shuffle(adultes)
        hommes = [e for e in adultes if e.sexe == "M" and rng.random() < 0.8]
        femmes = [e for e in adultes if e.sexe == "F" and rng.random() < 0.8]
        couples = []
        for h in hommes:
            # une femme d'une autre famille si possible, sinon une « nouvelle venue »
            choix = next((f for f in femmes if f.pere != h.pere
                          and abs(f.naissance.annee - h.naissance.annee) <= 10), None)
            if choix is not None:
                femmes.remove(choix)
            else:
                choix = monde.fondateur("F", h.naissance.annee + rng.randint(-6, 3), generation)
            couples.append((h, choix, monde.marier(h, choix)))
        for f in femmes[: len(femmes) // 3]:  # quelques femmes épousent un nouveau venu
            h = monde.fondateur("M", f.naissance.annee + rng.randint(-3, 6), generation)
            couples.append((h, f, monde.marier(h, f)))
    return monde


# --- Les arbres (vues bruitées du monde) -----------------------------------

@dataclass
class QualiteArbre:
    """Bruit d'un arbre : probabilités qu'un champ manque ou soit altéré."""
    p_date_manquante: float
    p_lieu_manquant: float
    p_annee_fausse: float
    p_prenom_omis: float
    p_variante_nom: float
    p_dit_affiche: float
    anglicise: bool


@dataclass
class PopulationSynthetique:
    personnes: list[Personne]
    identites: dict[tuple[int, str], int]   # (tree_id, person_id) -> id vrai
    n_individus_vrais: int


def _membres_arbre(monde: _Monde, racine: IndividuVrai, profondeur: int) -> list[int]:
    """Descendants de la racine et de ses conjoints (sur `profondeur` générations),
    avec leurs conjoints et les parents de ces conjoints."""
    gens = monde.gens
    membres: set[int] = set()
    niveau = {racine.id} | {u.conjoint for u in racine.unions}
    for _ in range(profondeur + 1):
        suivant: set[int] = set()
        for i in niveau:
            membres.add(i)
            for u in gens[i].unions:
                membres.add(u.conjoint)
                c = gens[u.conjoint]
                membres.update(x for x in (c.pere, c.mere) if x)
            suivant.update(gens[i].enfants)
        niveau = suivant
    return sorted(membres)


def _texte_date(rng: random.Random, d: DateVraie, q: QualiteArbre) -> str | None:
    if rng.random() < q.p_date_manquante:
        return None
    annee = d.annee + (rng.choice([-2, -1, 1, 2]) if rng.random() < q.p_annee_fausse else 0)
    forme = rng.random()
    if forme < 0.45:
        return f"{d.jour} {MOIS_GEDCOM[d.mois]} {annee}"
    if forme < 0.6:
        return f"{MOIS_GEDCOM[d.mois]} {annee}"
    if forme < 0.85:
        return str(annee)
    return f"ABT {annee}"


def _rendre_nom(rng: random.Random, i: IndividuVrai, q: QualiteArbre) -> tuple[str, str, str]:
    """(nom complet, prénoms, nom de famille) tels que l'arbre les écrit."""
    prenoms = list(i.prenoms)
    if len(prenoms) > 1 and rng.random() < q.p_prenom_omis:
        prenoms = prenoms[1:]                       # « Marie Louise » -> « Louise »
    if q.anglicise:
        prenoms = [ANGLAIS.get(normaliser(p), p) if rng.random() < 0.7 else p for p in prenoms]
    nom = i.nom_famille
    if nom in VARIANTES_NOMS_FAMILLE and rng.random() < q.p_variante_nom:
        nom = rng.choice(VARIANTES_NOMS_FAMILLE[nom])
    texte_prenoms = " ".join(prenoms)
    complet = f"{texte_prenoms} {nom}"
    if i.dit and rng.random() < q.p_dit_affiche:
        complet += (" dite " if i.sexe == "F" else " dit ") + i.dit
    return complet, texte_prenoms, nom


def _annee(texte: str | None) -> int | None:
    if not texte:
        return None
    return int(texte.split()[-1])


def _rendre_arbre(monde: _Monde, tree_id: int, membres: list[int], rng: random.Random,
                  q: QualiteArbre) -> tuple[list[Personne], dict[tuple[int, str], int]]:
    gens = monde.gens
    ens = set(membres)
    xrefs = {i: f"I{n + 1}" for n, i in enumerate(membres)}
    rendus: dict[int, dict] = {}
    for i in membres:
        v = gens[i]
        complet, prenoms, nom = _rendre_nom(rng, v, q)
        dates, lieux = {}, {}
        for fait, d, lieu in (("BIRT", v.naissance, v.lieu_naissance),
                              ("DEAT", v.deces, v.lieu_deces)):
            if d is None or (fait == "DEAT" and d.annee > 1900):
                continue
            texte = _texte_date(rng, d, q)
            if texte:
                dates[fait] = texte
            if lieu and rng.random() >= q.p_lieu_manquant:
                lieux[fait] = lieu
        # baptême : le jour même ou quelques jours après ; sépulture : peu après le décès
        if rng.random() < 0.5:
            dates["BAPM"] = _texte_date(rng, v.naissance, q) or ""
        if "DEAT" in dates and rng.random() < 0.4:
            dates["BURI"] = dates["DEAT"]
        dates = {f: t for f, t in dates.items() if t}
        alternatifs = []
        if v.sexe == "F" and v.unions and rng.random() < 0.2:
            mari = gens[v.unions[0].conjoint]
            alternatifs.append(f"{prenoms} {mari.nom_famille}")    # nom d'épouse (_MARNM)
        rendus[i] = {"nom": complet, "prenoms": prenoms, "nom_famille": nom,
                     "dates": dates, "lieux": lieux, "alternatifs": alternatifs}

    def proche(j: int) -> dict:
        return {"nom": rendus[j]["nom"], "nom_norm": normaliser(rendus[j]["nom"]),
                "naissance": _annee(rendus[j]["dates"].get("BIRT")), "person_id": xrefs[j]}

    personnes, identites = [], {}
    for i in membres:
        v, r = gens[i], rendus[i]
        faits = {f: _annee(t) for f, t in r["dates"].items()}
        mariages = []
        for u in v.unions:
            if u.conjoint not in ens:
                continue
            date = _texte_date(rng, u.date, q) if u.date else None
            mariages.append({
                "annee": _annee(date), "conjoint": rendus[u.conjoint]["nom"],
                "conjoint_norm": normaliser(rendus[u.conjoint]["nom"]),
                "conjoint_id": xrefs[u.conjoint], "date": date,
                "lieu": u.lieu if rng.random() >= q.p_lieu_manquant else None,
            })
        personnes.append(Personne(
            tree_id=tree_id, person_id=xrefs[i], nom_complet=r["nom"],
            nom_norm=normaliser(r["nom"]), sexe=v.sexe, faits=faits,
            mariages=mariages,
            parents=[proche(j) for j in (v.pere, v.mere) if j in ens],
            enfants=[proche(j) for j in v.enfants if j in ens],
            conjoints=[proche(u.conjoint) for u in v.unions if u.conjoint in ens],
            prenoms=r["prenoms"], nom_famille=r["nom_famille"],
            noms_alternatifs=r["alternatifs"], dates=r["dates"], lieux=r["lieux"],
        ))
        identites[(tree_id, xrefs[i])] = i
    return personnes, identites


def generer_population(
    graine: int = 0,
    n_fondateurs: int = 12,
    n_generations: int = 5,
    n_arbres: int = 6,
    profondeur_arbre: int = 3,
    taille_min_arbre: int = 30,
) -> PopulationSynthetique:
    """Génère une population synthétique multi-arbres (déterministe pour `graine`).

    Ordre de grandeur : n_fondateurs=12, n_generations=5 -> quelques milliers
    d'individus vrais ; chaque arbre en couvre une partie, avec recouvrements.
    """
    rng = random.Random(graine)
    monde = _construire_monde(rng, n_fondateurs, n_generations)

    # racines : surtout des fondateurs, parfois des descendants (arbres plus récents) ;
    # on retire au sort tant que l'arbre est trop petit.
    candidats = sorted(i.id for i in monde.gens.values() if i.unions and i.sexe == "M")
    fondateurs = [i for i in candidats if monde.gens[i].generation == 0]
    personnes, identites = [], {}
    for tree_id in range(1, n_arbres + 1):
        r = random.Random(graine * 1_000 + tree_id)
        meilleur: list[int] = []
        for _ in range(20):
            racine = monde.gens[r.choice(fondateurs if r.random() < 0.6 else candidats)]
            membres = _membres_arbre(monde, racine, profondeur_arbre)
            if len(membres) > len(meilleur):
                meilleur = membres
            if len(meilleur) >= taille_min_arbre:
                break
        membres = meilleur
        qualite = QualiteArbre(
            p_date_manquante=r.uniform(0.1, 0.5), p_lieu_manquant=r.uniform(0.2, 0.7),
            p_annee_fausse=r.uniform(0.0, 0.1), p_prenom_omis=r.uniform(0.0, 0.3),
            p_variante_nom=r.uniform(0.0, 0.4), p_dit_affiche=r.uniform(0.0, 0.6),
            anglicise=r.random() < 0.2,
        )
        ps, ids = _rendre_arbre(monde, tree_id, membres, r, qualite)
        personnes.extend(ps)
        identites.update(ids)
    return PopulationSynthetique(personnes, identites, len(monde.gens))
