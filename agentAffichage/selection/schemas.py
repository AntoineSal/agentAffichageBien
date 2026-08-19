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

Score de confiance : chaque candidat porte son propre confidence (0-1) et sa
justification, calculés par le modèle lui-même (voir prompt.py pour les 5
dimensions évaluées). ResultatSelection.candidats contient TOUS les candidats
identifiés, pas seulement ceux qu'il faut afficher — le filtrage par seuil est
une décision déterministe séparée (voir selection/confiance.py), pas laissée
au modèle : un candidat rejeté reste inspectable (utile pour le futur outil de
debug évoqué par l'utilisateur), au lieu de disparaître silencieusement.
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
# confidence/raison sont portés par chaque candidat, pas par ResultatSelection
# dans son ensemble : deux widgets d'une même réponse peuvent avoir des scores
# très différents (voir l'exemple de la spec : table 0.91, chart 0.78, stats 0.42).

_CONFIDENCE = Field(ge=0.0, le=1.0)


class WidgetImage(BaseModel):
    type: Literal["image"]
    confidence: float = _CONFIDENCE
    raison: str
    donnees: DonneesImage


class WidgetTable(BaseModel):
    type: Literal["table"]
    confidence: float = _CONFIDENCE
    raison: str
    donnees: DonneesTable


class WidgetCode(BaseModel):
    type: Literal["code"]
    confidence: float = _CONFIDENCE
    raison: str
    donnees: DonneesCode


class WidgetFichier(BaseModel):
    type: Literal["file"]
    confidence: float = _CONFIDENCE
    raison: str
    donnees: DonneesFichier


class WidgetCard(BaseModel):
    type: Literal["card"]
    confidence: float = _CONFIDENCE
    raison: str
    donnees: DonneesCard


class WidgetChart(BaseModel):
    type: Literal["chart"]
    confidence: float = _CONFIDENCE
    raison: str
    donnees: DonneesChart


class WidgetStats(BaseModel):
    type: Literal["stats"]
    confidence: float = _CONFIDENCE
    raison: str
    donnees: DonneesStats


class WidgetTimeline(BaseModel):
    type: Literal["timeline"]
    confidence: float = _CONFIDENCE
    raison: str
    donnees: DonneesTimeline


WidgetCandidat = Annotated[
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
    """Sortie de l'appel Mistral de sélection (selecteur.py). candidats contient
    TOUS les widgets envisagés, avec leur confidence — y compris ceux qui seront
    rejetés au filtrage (voir selection/confiance.py). Liste vide = aucun
    candidat envisagé, le résultat le plus fréquent et souvent le bon."""

    candidats: List[WidgetCandidat] = Field(default_factory=list, max_length=5)
