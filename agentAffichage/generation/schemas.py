"""
Structures de sortie de la génération avec outils d'affichage.

Volontairement minimales : les données de chaque widget restent les modèles
`Donnees*` déjà définis dans `selection/schemas.py` — aucune structure
parallèle n'est créée pour représenter un widget. Seule l'enveloppe change,
parce qu'elle ne porte plus les mêmes informations que dans l'ancien pipeline :

- pas de `confidence` ni de `raison` : dans cette architecture, c'est le modèle
  générateur lui-même qui décide d'appeler ou non un outil d'affichage. Il n'y a
  plus de second juge à qui demander un score, donc rien à filtrer ensuite. Un
  score ne sera réintroduit que si les tests montrent une surproduction de
  widgets (consigne explicite : ne pas l'ajouter par défaut).
- en revanche `ToolCallInvalide` est nouveau : avec des tool calls, un appel
  peut être refusé individuellement (outil inconnu, arguments invalides) sans
  que cela affecte le Markdown ni les autres widgets. Garder la trace de ces
  refus est ce qui rend l'échec debuggable au lieu d'être silencieux.
"""

from typing import List, NamedTuple, Optional, Protocol

from pydantic import BaseModel

from ..metriques import Metriques


class PorteurWidget(Protocol):
    """Ce dont `pipeline._construire_blocs_widgets()` a réellement besoin pour
    fabriquer un bloc ```widget:type{json}```. `WidgetGenere` (nouveau flux) et
    `WidgetCandidat` (ancien flux) satisfont tous les deux ce contrat — c'est ce
    qui permet aux deux pipelines de partager la même fonction de sérialisation
    sans qu'aucune ne connaisse l'autre."""

    @property
    def type(self) -> str: ...

    @property
    def donnees(self) -> BaseModel: ...


class WidgetGenere(NamedTuple):
    """Un tool call d'affichage validé. `type` est la clé du catalogue
    ("chart", "card"...), `donnees` une instance du modèle `Donnees*`
    correspondant, déjà validée par Pydantic."""

    type: str
    donnees: BaseModel


class ToolCallInvalide(NamedTuple):
    """Un tool call que l'on a refusé de rendre, et pourquoi. Le Markdown de la
    réponse n'est jamais affecté par ces refus."""

    nom_outil: str
    erreur: str
    arguments_bruts: str


class ResultatGeneration(NamedTuple):
    """Sortie d'un appel de génération avec outils d'affichage.

    `markdown` est toujours renseigné dès que l'appel a abouti, indépendamment
    du sort des widgets — c'est la garantie centrale de cette architecture.

    `metriques` vaut None dans les tests qui construisent ce NamedTuple à la
    main sans le préciser (défaut rétrocompatible) ; un vrai appel via
    `generer_avec_outils()` le renseigne toujours."""

    markdown: str
    widgets: List[WidgetGenere]
    invalides: List[ToolCallInvalide]
    metriques: Optional[Metriques] = None
