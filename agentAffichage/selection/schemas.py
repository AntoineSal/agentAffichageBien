"""
Modèles de données pour la sélection de widget.

Chaque modèle correspond exactement à la structure attendue par la fonction de
rendu associée dans agentAffichage/rendu/registre.py : pas de traduction entre
les deux, la sortie structurée de l'appel Mistral (phase 2) sera directement
sérialisable vers le bloc ```widget:type{json}``` consommé par le rendu.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ConditionsActuelles(BaseModel):
    """Snapshot météo du moment. Tous les champs sont optionnels : seuls ceux
    mentionnés dans le texte source doivent être remplis."""

    temperature: Optional[str] = None
    condition: Optional[str] = None
    apparent_temperature: Optional[str] = None
    wind_speed: Optional[str] = None
    humidity: Optional[str] = None


class JourPrevision(BaseModel):
    """Un jour de prévision. 'date' est la seule clé obligatoire : sans elle,
    rendu/registre.py ne peut pas afficher le jour (voir carte_meteo)."""

    date: str
    condition: Optional[str] = None
    temp_max: Optional[str] = None
    temp_min: Optional[str] = None


class DonneesWeather(BaseModel):
    """Le seul champ obligatoire est location : sans lieu identifié, le widget
    météo n'apporte rien de plus qu'une phrase de texte. forecast n'est pas
    borné à 3 éléments : autant de jours que mentionnés dans le texte source."""

    location: str
    current: Optional[ConditionsActuelles] = None
    forecast: List[JourPrevision] = Field(default_factory=list)


class ResultatSelection(BaseModel):
    """Sortie de l'appel Mistral de sélection (phase 2)."""

    widget_type: Literal["weather", "aucun"]
    donnees: Optional[DonneesWeather] = None

    @model_validator(mode="after")
    def _coherence_widget_donnees(self) -> "ResultatSelection":
        if self.widget_type == "aucun" and self.donnees is not None:
            raise ValueError('donnees doit être vide quand widget_type vaut "aucun".')
        if self.widget_type != "aucun" and self.donnees is None:
            raise ValueError("donnees est requis quand un widget est sélectionné.")
        return self
