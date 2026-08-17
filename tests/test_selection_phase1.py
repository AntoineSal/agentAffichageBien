"""
Fondations de la sélection (phase 1) : catalogue, schémas, prompt.
Aucun appel réseau ici — l'appel Mistral réel arrive en phase 2.
"""

import pytest
from pydantic import ValidationError

from agentAffichage.selection.catalogue import CATALOGUE
from agentAffichage.selection.prompt import construire_prompt_selection
from agentAffichage.selection.schemas import DonneesWeather, JourPrevision, ResultatSelection


# ─── schemas.py ──────────────────────────────────────────────────────────────

def test_donnees_weather_complet_valide():
    donnees = DonneesWeather(
        location="Paris",
        current={"temperature": "18°C", "condition": "Pluie légère", "humidity": "70%"},
        forecast=[{"date": "2026-08-18", "condition": "Ensoleillé", "temp_max": "22°C", "temp_min": "14°C"}],
    )
    assert donnees.location == "Paris"
    assert donnees.current.temperature == "18°C"
    assert donnees.forecast[0].date == "2026-08-18"


def test_donnees_weather_minimal_valide():
    """Seul location est obligatoire : le reste peut être totalement absent."""
    donnees = DonneesWeather(location="Lyon")
    assert donnees.current is None
    assert donnees.forecast == []


def test_donnees_weather_sans_location_invalide():
    with pytest.raises(ValidationError):
        DonneesWeather(current={"temperature": "18°C"})


def test_jour_prevision_sans_date_invalide():
    """rendu/registre.py ignore un jour sans date : le schéma doit l'interdire en amont."""
    with pytest.raises(ValidationError):
        JourPrevision(condition="Pluie", temp_max="15°C")


def test_forecast_non_limite_a_trois_jours():
    """Vérifie l'extensibilité voulue : pas de plafond figé dans le schéma."""
    donnees = DonneesWeather(
        location="Nice",
        forecast=[{"date": f"2026-08-{18 + i}"} for i in range(8)],
    )
    assert len(donnees.forecast) == 8


def test_resultat_selection_aucun_widget():
    resultat = ResultatSelection(widget_type="aucun")
    assert resultat.donnees is None


def test_resultat_selection_widget_sans_donnees_invalide():
    """Un widget choisi doit obligatoirement être accompagné de ses données."""
    with pytest.raises(ValidationError):
        ResultatSelection(widget_type="weather")


def test_resultat_selection_aucun_avec_donnees_invalide():
    """'aucun' avec des données serait incohérent : le validateur doit le refuser."""
    with pytest.raises(ValidationError):
        ResultatSelection(widget_type="aucun", donnees={"location": "Paris"})


# ─── catalogue.py + prompt.py ────────────────────────────────────────────────

def test_catalogue_contient_weather():
    cles = [w.cle for w in CATALOGUE]
    assert "weather" in cles


def test_prompt_liste_les_widgets_du_catalogue():
    prompt = construire_prompt_selection()
    for widget in CATALOGUE:
        assert widget.cle in prompt


def test_prompt_contient_la_regle_anti_invention():
    prompt = construire_prompt_selection()
    assert "N'invente" in prompt
    assert "aucun" in prompt
