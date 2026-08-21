"""
Fondations de la sélection : catalogue (8 widgets génériques), schémas
(union discriminée, candidats avec score de confiance), prompt. Aucun appel
réseau ici.
"""

import pytest
from pydantic import ValidationError

from agentAffichage.selection.catalogue import CATALOGUE
from agentAffichage.selection.prompt import construire_prompt_selection
from agentAffichage.selection.schemas import ResultatSelection

CLES_CATALOGUE = {w.cle for w in CATALOGUE}


def _candidat(type_, confidence=0.9, **donnees):
    return {"type": type_, "confidence": confidence, "raison": "test", "donnees": donnees}


# ─── schemas.py ──────────────────────────────────────────────────────────────

def test_candidats_vide_par_defaut():
    assert ResultatSelection().candidats == []


def test_un_candidat_stats_valide():
    resultat = ResultatSelection(candidats=[
        _candidat("stats", indicateurs=[{"label": "CA", "valeur": "420 M€"}]),
    ])
    assert resultat.candidats[0].type == "stats"
    assert resultat.candidats[0].confidence == 0.9
    assert resultat.candidats[0].donnees.indicateurs[0].label == "CA"


def test_plusieurs_candidats_de_types_differents_valide():
    resultat = ResultatSelection(candidats=[
        _candidat("card", titre="Apple Inc.", attributs=[]),
        _candidat("timeline", evenements=[{"date": "1976", "titre": "Fondation"}]),
    ])
    assert [c.type for c in resultat.candidats] == ["card", "timeline"]


def test_type_inconnu_invalide():
    with pytest.raises(ValidationError):
        ResultatSelection(candidats=[_candidat("carte_meteo")])


def test_donnees_incoherentes_avec_le_type_invalide():
    """Le discriminant "type" doit forcer le bon schéma de données : un candidat
    "card" avec des champs de "chart" doit être rejeté, pas silencieusement
    accepté avec des données tronquées."""
    with pytest.raises(ValidationError):
        ResultatSelection(candidats=[_candidat("card", type_graphique="ligne", series=[])])


def test_confidence_hors_bornes_invalide():
    with pytest.raises(ValidationError):
        ResultatSelection(candidats=[_candidat("stats", confidence=1.4, indicateurs=[])])


def test_candidat_sans_raison_invalide():
    with pytest.raises(ValidationError):
        ResultatSelection(candidats=[
            {"type": "stats", "confidence": 0.9, "donnees": {"indicateurs": []}},
        ])


def test_card_sans_titre_invalide():
    with pytest.raises(ValidationError):
        ResultatSelection(candidats=[_candidat("card", attributs=[])])


def test_timeline_evenement_sans_date_invalide():
    with pytest.raises(ValidationError):
        ResultatSelection(candidats=[
            _candidat("timeline", evenements=[{"titre": "sans date"}]),
        ])


def test_plus_de_cinq_candidats_invalide():
    """Garde-fou : max_length=5 sur la liste de candidats évalués."""
    with pytest.raises(ValidationError):
        ResultatSelection(candidats=[
            _candidat("stats", indicateurs=[{"label": "A", "valeur": "1"}]),
        ] * 6)


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


def test_prompt_contient_les_5_dimensions_du_score_de_confiance():
    prompt = construire_prompt_selection()
    for dimension in ("Pertinence", "Complétude", "Valeur ajoutée", "Clarté", "Redondance"):
        assert dimension in prompt


def test_prompt_precise_que_le_modele_ne_filtre_pas_lui_meme():
    prompt = construire_prompt_selection()
    assert "pas ta décision" in prompt or "N'applique toi-même aucun seuil" in prompt
