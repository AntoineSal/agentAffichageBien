"""
Catalogue déclaratif des widgets connus par la sélection.

Ajouter un widget ici (et son schéma dans schemas.py, sa fonction de rendu dans
rendu/registre.py, son entrée de dispatch dans rendu/afficheur.py) suffit à
l'intégrer partout : le prompt de sélection (voir prompt.py) se génère
automatiquement depuis cette liste, sans rien modifier d'autre.
"""

from dataclasses import dataclass
from typing import Type

from pydantic import BaseModel

from .schemas import DonneesWeather


@dataclass(frozen=True)
class DescripteurWidget:
    cle: str
    description: str
    schema: Type[BaseModel]


CATALOGUE = [
    DescripteurWidget(
        cle="weather",
        description=(
            "La réponse contient une prévision ou un relevé météo concret "
            "(température, conditions, prévisions à venir) pour un lieu identifié."
        ),
        schema=DonneesWeather,
    ),
]
