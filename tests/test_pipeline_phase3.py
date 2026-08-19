"""
pipeline.py : orchestration sélection -> filtrage par seuil de confiance ->
rendu (0, 1 ou plusieurs widgets), et fallback en cas d'échec.
selectionner_widget est simulée partout ici — aucun appel réseau.
"""

from unittest.mock import patch

from agentAffichage.pipeline import genererAffichage
from agentAffichage.selection.confiance import SEUIL_AFFICHAGE
from agentAffichage.selection.schemas import ResultatSelection


def _candidat(type_, confidence, **donnees):
    return {"type": type_, "confidence": confidence, "raison": "test", "donnees": donnees}


@patch("agentAffichage.pipeline.selectionner_widget")
def test_candidat_au_dessus_du_seuil_est_rendu(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection(candidats=[
        _candidat("stats", SEUIL_AFFICHAGE + 0.1, indicateurs=[{"label": "CA", "valeur": "420 M€"}]),
    ])

    html = genererAffichage("Le chiffre d'affaires est de 420 M€.")

    assert "420 M" in html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_candidat_sous_le_seuil_nest_pas_rendu(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection(candidats=[
        _candidat("stats", SEUIL_AFFICHAGE - 0.1, indicateurs=[{"label": "CA", "valeur": "420 M€"}]),
    ])

    html = genererAffichage("Bonjour, comment vas-tu ?")

    # Le texte source reste affiché (repli), mais aucune carte de stats n'est
    # injectée : la ligne "CA" du candidat rejeté ne doit apparaître nulle part.
    assert "Bonjour" in html
    assert "widget:" not in html
    assert "CA" not in html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_seuls_les_candidats_retenus_sont_rendus_parmi_plusieurs(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection(candidats=[
        _candidat("card", 0.91, titre="Apple Inc.", attributs=[{"label": "PDG", "valeur": "Tim Cook"}]),
        _candidat("stats", 0.42, indicateurs=[{"label": "Fondation", "valeur": "1976"}]),
    ])

    html = genererAffichage("Petit résumé d'Apple.")

    assert "Apple Inc." in html and "Tim Cook" in html
    assert "widget:stats" not in html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_aucun_candidat_rend_juste_le_texte(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection()

    html = genererAffichage("Bonjour, comment vas-tu ?")

    assert "Bonjour" in html
    assert "widget:" not in html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_echec_de_la_selection_retombe_sur_le_texte_brut(mock_selectionner, capsys):
    mock_selectionner.side_effect = RuntimeError("panne simulée")

    html = genererAffichage("Bonjour, comment vas-tu ?")

    assert "Bonjour" in html
    assert "widget:" not in html
    assert "panne simulée" in capsys.readouterr().err


@patch("agentAffichage.pipeline.selectionner_widget")
def test_cle_api_transmise_a_la_selection(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection()

    genererAffichage("Texte quelconque.", api_key="cle-de-test")

    args, kwargs = mock_selectionner.call_args
    assert args[0] == "Texte quelconque."
    assert kwargs["api_key"] == "cle-de-test"
