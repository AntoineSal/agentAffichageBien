"""
selecteur.py (phase 2) : câblage de l'appel Mistral. Le client mistralai est
simulé partout ici — aucun de ces tests n'a besoin d'une vraie clé API ni
d'accès réseau. La vérification avec un vrai appel Mistral se fait à part
(voir agentAffichage/README.md), une fois une clé API disponible.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agentAffichage.selection.schemas import ResultatSelection
from agentAffichage.selection.selecteur import selectionner_widget


def _reponse_simulee(resultat):
    """Reproduit la forme réelle : reponse.choices[0].message.parsed"""
    message = SimpleNamespace(parsed=resultat)
    choix = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choix])


def test_leve_une_erreur_sans_cle_api(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Clé API"):
        selectionner_widget("Il fait beau à Paris.", api_key=None)


@patch("agentAffichage.selection.selecteur.Mistral")
def test_leve_une_erreur_claire_si_locale_non_utf8(mock_mistral_cls, monkeypatch):
    """Reproduit le cas constaté le 17/08/2026 (LANG/LC_ALL absents du shell) :
    on doit obtenir une erreur explicite, jamais une UnicodeEncodeError brute
    remontant de l'intérieur du SDK — et aucun appel réseau ne doit partir."""
    monkeypatch.setattr("agentAffichage.selection.selecteur.locale.getpreferredencoding", lambda: "US-ASCII")

    with pytest.raises(RuntimeError, match="PYTHONUTF8"):
        selectionner_widget("Il fait beau à Paris.", api_key="cle-de-test")

    mock_mistral_cls.assert_not_called()


@patch("agentAffichage.selection.selecteur.Mistral")
def test_renvoie_le_resultat_parse(mock_mistral_cls):
    attendu = ResultatSelection()
    mock_client = MagicMock()
    mock_client.chat.parse.return_value = _reponse_simulee(attendu)
    mock_mistral_cls.return_value = mock_client

    resultat = selectionner_widget("Bonjour, comment vas-tu ?", api_key="cle-de-test")

    assert resultat is attendu
    mock_mistral_cls.assert_called_once_with(api_key="cle-de-test")


@patch("agentAffichage.selection.selecteur.Mistral")
def test_appelle_mistral_avec_le_bon_format_et_les_bons_messages(mock_mistral_cls):
    mock_client = MagicMock()
    mock_client.chat.parse.return_value = _reponse_simulee(ResultatSelection())
    mock_mistral_cls.return_value = mock_client

    selectionner_widget("Il fait 18°C à Paris.", api_key="cle-de-test")

    _, kwargs = mock_client.chat.parse.call_args
    assert kwargs["response_format"] is ResultatSelection
    assert kwargs["messages"][0]["role"] == "system"
    assert '"stats"' in kwargs["messages"][0]["content"]
    assert kwargs["messages"][1] == {"role": "user", "content": "Il fait 18°C à Paris."}


@patch("agentAffichage.selection.selecteur.Mistral")
def test_leve_une_erreur_si_mistral_ne_renvoie_rien_dexploitable(mock_mistral_cls):
    mock_client = MagicMock()
    mock_client.chat.parse.return_value = _reponse_simulee(None)
    mock_mistral_cls.return_value = mock_client

    with pytest.raises(RuntimeError, match="sortie exploitable"):
        selectionner_widget("Texte quelconque.", api_key="cle-de-test")
