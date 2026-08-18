"""
pipeline.py (phase 3) : orchestration sélection -> rendu, et fallback en cas
d'échec. selectionner_widget est simulée partout ici — aucun appel réseau.
"""

from unittest.mock import patch

from agentAffichage.pipeline import genererAffichage
from agentAffichage.selection.schemas import DonneesWeather, ResultatSelection


@patch("agentAffichage.pipeline.selectionner_widget")
def test_widget_choisi_est_rendu(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection(
        widget_type="weather",
        donnees=DonneesWeather(location="Paris", current={"temperature": "18°C"}),
    )

    html = genererAffichage("Bien sûr ! Voici la météo à Paris.")

    assert "Paris" in html
    assert "18°C" in html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_aucun_widget_rend_juste_le_texte(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection(widget_type="aucun")

    html = genererAffichage("Bonjour, comment vas-tu ?")

    assert "Bonjour" in html
    assert "linear-gradient(135deg,#FEF3E2" not in html  # pas de carte météo


@patch("agentAffichage.pipeline.selectionner_widget")
def test_echec_de_la_selection_retombe_sur_le_texte_brut(mock_selectionner, capsys):
    mock_selectionner.side_effect = RuntimeError("panne simulée")

    html = genererAffichage("Bonjour, comment vas-tu ?")

    assert "Bonjour" in html
    assert "linear-gradient(135deg,#FEF3E2" not in html
    assert "panne simulée" in capsys.readouterr().err


@patch("agentAffichage.pipeline.selectionner_widget")
def test_cle_api_transmise_a_la_selection(mock_selectionner):
    mock_selectionner.return_value = ResultatSelection(widget_type="aucun")

    genererAffichage("Texte quelconque.", api_key="cle-de-test")

    args, kwargs = mock_selectionner.call_args
    assert args[0] == "Texte quelconque."
    assert kwargs["api_key"] == "cle-de-test"
