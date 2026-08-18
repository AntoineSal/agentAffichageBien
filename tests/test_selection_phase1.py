"""
Fondations de la sélection : catalogue (8 widgets génériques), schémas
(union discriminée, multi-widgets), prompt. Aucun appel réseau ici.
"""

import pytest
from pydantic import ValidationError

from agentAffichage.selection.catalogue import CATALOGUE
from agentAffichage.selection.prompt import construire_prompt_selection
from agentAffichage.selection.schemas import ResultatSelection

CLES_CATALOGUE = {w.cle for w in CATALOGUE}


# ─── schemas.py ──────────────────────────────────────────────────────────────

def test_widgets_vide_par_defaut():
    assert ResultatSelection().widgets == []


def test_un_widget_stats_valide():
    resultat = ResultatSelection(widgets=[
        {"type": "stats", "donnees": {"indicateurs": [{"label": "CA", "valeur": "420 M€"}]}},
    ])
    assert resultat.widgets[0].type == "stats"
    assert resultat.widgets[0].donnees.indicateurs[0].label == "CA"


def test_plusieurs_widgets_de_types_differents_valide():
    resultat = ResultatSelection(widgets=[
        {"type": "card", "donnees": {"titre": "Apple Inc.", "attributs": []}},
        {"type": "timeline", "donnees": {"evenements": [{"date": "1976", "titre": "Fondation"}]}},
    ])
    assert [w.type for w in resultat.widgets] == ["card", "timeline"]


def test_type_inconnu_invalide():
    with pytest.raises(ValidationError):
        ResultatSelection(widgets=[{"type": "carte_meteo", "donnees": {}}])


def test_donnees_incoherentes_avec_le_type_invalide():
    """Le discriminant "type" doit forcer le bon schéma de données : un widget
    "card" avec des champs de "chart" doit être rejeté, pas silencieusement
    accepté avec des données tronquées."""
    with pytest.raises(ValidationError):
        ResultatSelection(widgets=[
            {"type": "card", "donnees": {"type_graphique": "ligne", "series": []}},
        ])


def test_card_sans_titre_invalide():
    with pytest.raises(ValidationError):
        ResultatSelection(widgets=[{"type": "card", "donnees": {"attributs": []}}])


def test_timeline_evenement_sans_date_invalide():
    with pytest.raises(ValidationError):
        ResultatSelection(widgets=[
            {"type": "timeline", "donnees": {"evenements": [{"titre": "sans date"}]}},
        ])


def test_plus_de_trois_widgets_invalide():
    """Garde-fou : max_length=3 sur la liste, la sélection doit rester rare."""
    with pytest.raises(ValidationError):
        ResultatSelection(widgets=[
            {"type": "stats", "donnees": {"indicateurs": [{"label": "A", "valeur": "1"}]}},
        ] * 4)


# ─── catalogue.py ─────────────────────────────────────────────────────────────

def test_catalogue_contient_exactement_les_8_widgets_attendus():
    assert CLES_CATALOGUE == {
        "image", "table", "code", "file", "card", "chart", "stats", "timeline",
    }


def test_catalogue_ne_contient_plus_weather():
    assert "weather" not in CLES_CATALOGUE


# ─── prompt.py ────────────────────────────────────────────────────────────────

def test_prompt_liste_les_8_widgets_du_catalogue():
    prompt = construire_prompt_selection()
    for cle in CLES_CATALOGUE:
        assert f'"{cle}"' in prompt


def test_prompt_contient_la_regle_anti_faux_positifs():
    prompt = construire_prompt_selection()
    assert "faux positifs" in prompt.lower()
    assert "n'invente" in prompt.lower() or "jamais" in prompt.lower()


def test_prompt_contient_lexemple_temperature_unique_vs_serie():
    prompt = construire_prompt_selection()
    assert "15°C" in prompt
