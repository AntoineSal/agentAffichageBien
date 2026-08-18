"""
Modèles de données pour la sélection de widget.

8 widgets génériques (IMAGE, TABLE, CODE, FILE, CARD, CHART, STATS, TIMELINE) —
volontairement pas de widgets spécifiques à un domaine (météo, calendrier...) :
n'importe quel domaine se représente via l'un de ces 8 types structurels.

Chaque modèle correspond exactement à la structure attendue par la fonction de
rendu associée dans agentAffichage/rendu/registre.py : pas de traduction entre
les deux, la sortie structurée de l'appel Mistral (selecteur.py) sera
directement sérialisable vers les blocs ```widget:type{json}``` consommés par
le rendu.

Une réponse peut contenir 0, 1, ou plusieurs widgets (rarement plusieurs — la
sélection doit le justifier, voir prompt.py) : ResultatSelection.widgets est
une liste, plafonnée à 3 comme garde-fou contre une sortie qui déraperait.
"""

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ─── IMAGE ───────────────────────────────────────────────────────────────────

class DonneesImage(BaseModel):
    """url doit provenir d'une image Markdown ou d'une URL déjà présente dans
    le texte — jamais inventée."""

    url: str
    alt: Optional[str] = None
    legende: Optional[str] = None
    source: Optional[str] = None


# ─── TABLE ───────────────────────────────────────────────────────────────────

class DonneesTable(BaseModel):
    titre: Optional[str] = None
    colonnes: List[str]
    lignes: List[List[str]] = Field(default_factory=list)


# ─── CODE ────────────────────────────────────────────────────────────────────

class DonneesCode(BaseModel):
    code: str
    langage: Optional[str] = None
    titre: Optional[str] = None


# ─── FILE ────────────────────────────────────────────────────────────────────

class DonneesFichier(BaseModel):
    """url doit être une référence de fichier réellement présente dans le
    texte (ex: un lien Markdown) — jamais inventée."""

    url: str
    nom: Optional[str] = None
    type_fichier: Optional[str] = None
    taille: Optional[str] = None


# ─── CARD ────────────────────────────────────────────────────────────────────

class AttributCard(BaseModel):
    label: str
    valeur: str


class DonneesCard(BaseModel):
    titre: str
    sous_titre: Optional[str] = None
    attributs: List[AttributCard] = Field(default_factory=list)


# ─── CHART ───────────────────────────────────────────────────────────────────

class SerieChart(BaseModel):
    nom: Optional[str] = None
    valeurs: List[float]


class DonneesChart(BaseModel):
    titre: Optional[str] = None
    type_graphique: Literal["ligne", "barres", "secteurs", "nuage_points"]
    categories: List[str] = Field(default_factory=list)
    series: List[SerieChart]
    unite: Optional[str] = None


# ─── STATS ───────────────────────────────────────────────────────────────────

class Indicateur(BaseModel):
    label: str
    valeur: str
    tendance: Optional[str] = None


class DonneesStats(BaseModel):
    titre: Optional[str] = None
    indicateurs: List[Indicateur]


# ─── TIMELINE ────────────────────────────────────────────────────────────────

class EvenementTimeline(BaseModel):
    date: str
    titre: str
    description: Optional[str] = None


class DonneesTimeline(BaseModel):
    titre: Optional[str] = None
    evenements: List[EvenementTimeline]


# ─── Enveloppe (union discriminée sur "type") ────────────────────────────────

class WidgetImage(BaseModel):
    type: Literal["image"]
    donnees: DonneesImage


class WidgetTable(BaseModel):
    type: Literal["table"]
    donnees: DonneesTable


class WidgetCode(BaseModel):
    type: Literal["code"]
    donnees: DonneesCode


class WidgetFichier(BaseModel):
    type: Literal["file"]
    donnees: DonneesFichier


class WidgetCard(BaseModel):
    type: Literal["card"]
    donnees: DonneesCard


class WidgetChart(BaseModel):
    type: Literal["chart"]
    donnees: DonneesChart


class WidgetStats(BaseModel):
    type: Literal["stats"]
    donnees: DonneesStats


class WidgetTimeline(BaseModel):
    type: Literal["timeline"]
    donnees: DonneesTimeline


WidgetSelectionne = Annotated[
    Union[
        WidgetImage,
        WidgetTable,
        WidgetCode,
        WidgetFichier,
        WidgetCard,
        WidgetChart,
        WidgetStats,
        WidgetTimeline,
    ],
    Field(discriminator="type"),
]


class ResultatSelection(BaseModel):
    """Sortie de l'appel Mistral de sélection (selecteur.py). Liste vide =
    aucun widget, le résultat le plus fréquent et souvent le bon (voir la
    philosophie conservative de prompt.py)."""

    widgets: List[WidgetSelectionne] = Field(default_factory=list, max_length=3)
