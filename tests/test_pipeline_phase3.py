"""
pipeline.py : orchestration sélection -> rendu (0, 1 ou plusieurs widgets), et
fallback en cas d'échec. selectionner_widget est simulée partout ici — aucun
appel réseau.
"""

from unittest.mock import patch

from agentAffichage.pipeline import genererAffichage
from agentAffichage.selection.schemas import ResultatSelection


@patch("agentAffichage.pipeline.selectionner_widget")
def test_un_widget_choisi_est_rendu(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection(widgets=[
        {"type": "stats", "donnees": {"indicateurs": [{"label": "CA", "valeur": "420 M€"}]}},
    ])

    html = genererAffichage("Le chiffre d'affaires est de 420 M€.")

    assert "420 M" in html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_plusieurs_widgets_choisis_sont_tous_rendus(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection(widgets=[
        {"type": "card", "donnees": {"titre": "Apple Inc.", "attributs": [{"label": "PDG", "valeur": "Tim Cook"}]}},
        {"type": "timeline", "donnees": {"evenements": [{"date": "1976", "titre": "Fondation"}]}},
    ])

    html = genererAffichage("Petit historique d'Apple.")

    assert "Apple Inc." in html and "Tim Cook" in html
    assert "1976" in html and "Fondation" in html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_aucun_widget_rend_juste_le_texte(mock_selectionner):
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
