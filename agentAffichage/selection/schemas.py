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

from typing import Annotated, Any, List, Literal, Optional, Union

from pydantic import BaseModel, BeforeValidator, Field, model_validator


def _en_texte(valeur: Any) -> Any:
    """Convertit un nombre en texte, laisse tout le reste tel quel.

    Pydantic v2 convertit "430" en float mais refuse 1957 en str. Or un modèle
    qui remplit un widget envoie très naturellement des nombres pour ce qui EST
    un nombre : `{"date": 1957}`, `{"valeur": 12742}`, une cellule de tableau à
    1425000000. Sans cette conversion, ces widgets — parfaitement légitimes —
    étaient silencieusement rejetés (constaté le 20/08/2026 en simulant les
    sorties plausibles du modèle sur les questions de test).

    Le rendu attend du texte partout (`html.escape`), donc la conversion se fait
    ici, au seul endroit qui décrit le format — pas dans chaque fonction de rendu.
    bool n'est volontairement pas converti : `True` n'est pas une valeur
    affichable, et le laisser échouer à la validation est le bon comportement.
    """
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, (int, float)):
        return str(valeur)
    return valeur


# Pour tout champ qui porte une VALEUR affichée (par opposition à une URL, du
# code ou un identifiant technique, jamais numériques).
TexteSouple = Annotated[str, BeforeValidator(_en_texte)]


# Une unité est un symbole ("USD", "%", "millions d'habitants"), pas une phrase.
UNITE_MAX = 24


def _unite_courte(valeur: Any) -> Any:
    """Écarte une unité qui n'en est manifestement pas une.

    Constaté le 21/08/2026 : le modèle a rempli `unite` avec un paragraphe
    entier de contexte et de sources. Rejeter tout le graphique pour ça serait
    disproportionné — `unite` est un champ accessoire — donc la valeur aberrante
    est simplement abandonnée et le graphique reste affichable. La contrainte
    figure aussi dans le schéma JSON envoyé au modèle (voir DonneesChart.unite),
    ce qui décourage le problème en amont.
    """
    if isinstance(valeur, str) and len(valeur.strip()) > UNITE_MAX:
        return None
    return valeur


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
    colonnes: List[TexteSouple]
    lignes: List[List[TexteSouple]] = Field(default_factory=list)


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
    label: TexteSouple
    valeur: TexteSouple


class DonneesCard(BaseModel):
    titre: str
    sous_titre: Optional[str] = None
    attributs: List[AttributCard] = Field(default_factory=list)


# ─── CHART ───────────────────────────────────────────────────────────────────

class SerieChart(BaseModel):
    nom: Optional[str] = None
    valeurs: List[float] = Field(
        min_length=1,
        description="Une valeur par catégorie, dans le même ordre que categories.",
    )


# Attention : la docstring d'un modèle part telle quelle dans le schéma JSON
# envoyé au modèle (champ "description"). Les notes de développement vivent donc
# ici, en commentaire, et pas dans la docstring de la classe.
#
# Le renderer associe positionnellement `categories[i]` à `valeurs[i]` (labels
# Chart.js). Un graphique dont les catégories manquent, ou ne correspondent pas
# en nombre aux valeurs, s'affiche donc avec un axe muet ou décalé — constaté le
# 21/08/2026, deux fois : `categories: []` alors que 9 valeurs étaient fournies.
# La cohérence est vérifiée ici plutôt qu'au rendu, pour que l'appel soit refusé
# avec un message explicite (visible dans la console de génération du sandbox)
# au lieu de produire silencieusement un graphique faux.
class DonneesChart(BaseModel):
    """Graphique : chaque valeur d'une série correspond à la catégorie de même
    rang. Toutes les séries ont donc exactement autant de valeurs qu'il y a de
    catégories."""

    titre: Optional[str] = None
    type_graphique: Literal["ligne", "barres", "secteurs", "nuage_points"]
    # Les catégories sont très souvent des années : 2015 doit passer comme "2015".
    categories: List[TexteSouple] = Field(
        min_length=1,
        description=(
            "Étiquette de chaque point, dans l'ordre (années, noms de pays, "
            "catégories...). Obligatoire, et de même longueur que les valeurs "
            "de chaque série."
        ),
    )
    series: List[SerieChart] = Field(min_length=1)
    unite: Annotated[Optional[str], BeforeValidator(_unite_courte)] = Field(
        default=None,
        max_length=UNITE_MAX,
        description=(
            "Unité des valeurs, sous forme de symbole court uniquement "
            "(ex: \"USD\", \"%\", \"millions\"). Jamais une phrase, jamais une source."
        ),
    )

    @model_validator(mode="after")
    def _valeurs_alignees_sur_categories(self) -> "DonneesChart":
        attendu = len(self.categories)
        for i, serie in enumerate(self.series):
            if len(serie.valeurs) != attendu:
                nom = serie.nom or f"série {i + 1}"
                raise ValueError(
                    f"« {nom} » porte {len(serie.valeurs)} valeurs pour "
                    f"{attendu} catégorie(s) : chaque valeur doit avoir son étiquette."
                )
        return self


# ─── STATS ───────────────────────────────────────────────────────────────────

class Indicateur(BaseModel):
    label: TexteSouple
    valeur: TexteSouple
    tendance: Optional[TexteSouple] = None


class DonneesStats(BaseModel):
    titre: Optional[str] = None
    indicateurs: List[Indicateur]


# ─── TIMELINE ────────────────────────────────────────────────────────────────

class EvenementTimeline(BaseModel):
    # date est très souvent une année seule : 1969 doit passer comme "1969".
    date: TexteSouple
    titre: TexteSouple
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
