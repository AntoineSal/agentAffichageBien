"""
Nouvelle architecture : widgets produits par tool calls du modèle générateur.
Le client Mistral est simulé partout — aucun appel réseau, aucune clé requise.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agentAffichage.generation.generateur import convertir_tool_calls, generer_avec_outils
from agentAffichage.generation.outils import (
    SCHEMA_PAR_CLE,
    cle_depuis_nom_outil,
    construire_outils,
    nom_outil,
)
from agentAffichage.selection.catalogue import CATALOGUE


def _tool_call(nom, arguments):
    """Reproduit la forme réelle : appel.function.name / appel.function.arguments."""
    return SimpleNamespace(function=SimpleNamespace(name=nom, arguments=arguments))


def _reponse(content, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# ─── Déclaration des outils ──────────────────────────────────────────────────

def test_les_8_widgets_du_catalogue_sont_declares():
    noms = {o["function"]["name"] for o in construire_outils()}
    assert noms == {nom_outil(w.cle) for w in CATALOGUE}
    assert len(noms) == 8


def test_schema_interdit_les_champs_hors_schema():
    """additionalProperties:false doit être posé partout, y compris dans les
    modèles imbriqués — c'est ce qui empêche le modèle d'inventer un champ."""
    chart = next(o for o in construire_outils() if o["function"]["name"] == "afficher_chart")
    params = chart["function"]["parameters"]
    assert params["additionalProperties"] is False
    assert params["$defs"]["SerieChart"]["additionalProperties"] is False


def test_description_de_loutil_porte_les_regles_du_catalogue():
    card = next(o for o in construire_outils() if o["function"]["name"] == "afficher_card")
    description = card["function"]["description"]
    assert "UTILISER QUAND" in description
    assert "NE PAS UTILISER QUAND" in description


def test_outil_inconnu_nest_pas_reconnu():
    assert cle_depuis_nom_outil("afficher_chart") == "chart"
    assert cle_depuis_nom_outil("afficher_carte_meteo") is None
    assert cle_depuis_nom_outil("supprimer_fichiers") is None


def test_chaque_widget_du_catalogue_a_son_modele_de_donnees():
    assert set(SCHEMA_PAR_CLE) == {w.cle for w in CATALOGUE}


# ─── Conversion des tool calls ───────────────────────────────────────────────

def test_arguments_en_dict_sont_acceptes():
    widgets, invalides = convertir_tool_calls([
        _tool_call("afficher_card", {"titre": "Apple Inc.", "attributs": []}),
    ])
    assert invalides == []
    assert widgets[0].type == "card"
    assert widgets[0].donnees.titre == "Apple Inc."


def test_arguments_en_chaine_json_sont_acceptes():
    """Le SDK type arguments en Union[Dict, str] : les deux doivent passer."""
    widgets, invalides = convertir_tool_calls([
        _tool_call("afficher_card", json.dumps({"titre": "Tesla", "attributs": []})),
    ])
    assert invalides == []
    assert widgets[0].donnees.titre == "Tesla"


def test_json_invalide_est_ecarte_sans_exception():
    widgets, invalides = convertir_tool_calls([_tool_call("afficher_card", "{pas du json")])
    assert widgets == []
    assert len(invalides) == 1
    assert invalides[0].nom_outil == "afficher_card"


def test_outil_invente_est_ecarte():
    widgets, invalides = convertir_tool_calls([_tool_call("afficher_meteo", {"ville": "Paris"})])
    assert widgets == []
    assert "inconnu" in invalides[0].erreur


def test_arguments_ne_respectant_pas_le_schema_sont_ecartes():
    """titre est obligatoire pour une card : son absence doit être refusée."""
    widgets, invalides = convertir_tool_calls([_tool_call("afficher_card", {"attributs": []})])
    assert widgets == []
    assert "invalides" in invalides[0].erreur


def test_un_appel_invalide_nempeche_pas_les_autres():
    widgets, invalides = convertir_tool_calls([
        _tool_call("afficher_card", {"titre": "Valide", "attributs": []}),
        _tool_call("afficher_card", "{cassé"),
        _tool_call("afficher_stats", {"indicateurs": [{"label": "CA", "valeur": "420 M€"}]}),
    ])
    assert [w.type for w in widgets] == ["card", "stats"]
    assert len(invalides) == 1


def test_aucun_tool_call_donne_aucun_widget():
    assert convertir_tool_calls(None) == ([], [])
    assert convertir_tool_calls([]) == ([], [])


# ─── Appel Mistral ───────────────────────────────────────────────────────────

@patch("agentAffichage.generation.generateur.creer_client")
def test_appel_fournit_les_outils_et_laisse_le_modele_decider(mock_client):
    client = MagicMock()
    client.chat.complete.return_value = _reponse("Bonjour !")
    mock_client.return_value = client

    generer_avec_outils("Salut", api_key="cle-de-test")

    kwargs = client.chat.complete.call_args.kwargs
    assert len(kwargs["tools"]) == 8
    # "auto" est essentiel : "any"/"required" forceraient un widget à chaque réponse.
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["parallel_tool_calls"] is True
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1] == {"role": "user", "content": "Salut"}


@patch("agentAffichage.generation.generateur.creer_client")
def test_reponse_sans_widget_rend_le_markdown_seul(mock_client):
    client = MagicMock()
    client.chat.complete.return_value = _reponse("Il fait 15°C dehors.")
    mock_client.return_value = client

    resultat = generer_avec_outils("Quel temps ?", api_key="cle-de-test")

    assert resultat.markdown == "Il fait 15°C dehors."
    assert resultat.widgets == []
    assert resultat.invalides == []


@patch("agentAffichage.generation.generateur.creer_client")
def test_content_absent_ne_plante_pas(mock_client):
    """content est typé OptionalNullable dans le SDK : None doit être toléré."""
    client = MagicMock()
    client.chat.complete.return_value = _reponse(None)
    mock_client.return_value = client

    assert generer_avec_outils("Salut", api_key="cle-de-test").markdown == ""


@patch("agentAffichage.generation.generateur.creer_client")
def test_content_en_liste_de_chunks_est_recompose(mock_client):
    """content est typé Union[str, List[ContentChunk]] : les deux doivent passer."""
    client = MagicMock()
    client.chat.complete.return_value = _reponse([
        SimpleNamespace(text="Bonjour "),
        SimpleNamespace(text="le monde."),
    ])
    mock_client.return_value = client

    assert generer_avec_outils("Salut", api_key="cle-de-test").markdown == "Bonjour le monde."


@patch("agentAffichage.generation.generateur.creer_client")
def test_plusieurs_widgets_dans_une_meme_reponse(mock_client):
    client = MagicMock()
    client.chat.complete.return_value = _reponse(
        "Voici le résumé.",
        [
            _tool_call("afficher_card", {"titre": "SpaceX", "attributs": []}),
            _tool_call("afficher_timeline", {"evenements": [{"date": "2002", "titre": "Fondation"}]}),
        ],
    )
    mock_client.return_value = client

    resultat = generer_avec_outils("Parle-moi de SpaceX", api_key="cle-de-test")

    assert [w.type for w in resultat.widgets] == ["card", "timeline"]


@patch("agentAffichage.generation.generateur.creer_client")
def test_widget_invalide_ne_fait_pas_disparaitre_le_markdown(mock_client, capsys):
    client = MagicMock()
    client.chat.complete.return_value = _reponse(
        "Réponse utile.",
        [_tool_call("afficher_chart", {"type_graphique": "camembert_invalide", "series": []})],
    )
    mock_client.return_value = client

    resultat = generer_avec_outils("Question", api_key="cle-de-test")

    assert resultat.markdown == "Réponse utile."
    assert resultat.widgets == []
    assert len(resultat.invalides) == 1
    assert "widget ignoré" in capsys.readouterr().err
