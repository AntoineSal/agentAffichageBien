"""
Pipeline du nouveau flux (genererAffichageAvecOutils) et comparaison avec
l'ancien (genererAffichage). Tout est simulé — aucun appel réseau.
"""

from unittest.mock import patch

from agentAffichage.generation.schemas import (
    ResultatGeneration,
    ToolCallInvalide,
    WidgetGenere,
)
from agentAffichage.metriques import Metriques
from agentAffichage.pipeline import genererAffichage, genererAffichageAvecOutils
from agentAffichage.selection.schemas import (
    DonneesCard,
    DonneesImage,
    DonneesStats,
    ResultatSelection,
)
from agentAffichage.selection.selecteur import AppelSelection


def _appel(resultat, metriques=None):
    return AppelSelection(resultat, metriques or Metriques())


def _generation(markdown, widgets=None, invalides=None):
    return ResultatGeneration(
        markdown=markdown, widgets=widgets or [], invalides=invalides or []
    )


# ─── Les trois cas demandés ──────────────────────────────────────────────────

@patch("agentAffichage.pipeline.generer_avec_outils")
def test_markdown_seul(mock_generer):
    mock_generer.return_value = _generation("Il fait **15°C** dehors.")

    resultat = genererAffichageAvecOutils("Quel temps fait-il ?")

    assert "15°C" in resultat.html
    assert "widget:" not in resultat.html
    assert resultat.erreur is None


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_markdown_plus_un_widget(mock_generer):
    mock_generer.return_value = _generation(
        "Voici les indicateurs du mois.",
        [WidgetGenere("stats", DonneesStats(indicateurs=[
            {"label": "CA", "valeur": "420 M€"},
            {"label": "Marge", "valeur": "24%"},
        ]))],
    )

    resultat = genererAffichageAvecOutils("Résultats du mois ?")

    assert "Voici les indicateurs" in resultat.html
    assert "420 M" in resultat.html and "Marge" in resultat.html


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_markdown_plus_plusieurs_widgets(mock_generer):
    mock_generer.return_value = _generation(
        "Résumé de l'entreprise.",
        [
            WidgetGenere("card", DonneesCard(titre="SpaceX", attributs=[
                {"label": "Fondation", "valeur": "2002"},
            ])),
            WidgetGenere("stats", DonneesStats(indicateurs=[
                {"label": "Lancements", "valeur": "96"},
            ])),
        ],
    )

    resultat = genererAffichageAvecOutils("Parle-moi de SpaceX")

    assert "SpaceX" in resultat.html
    assert "Lancements" in resultat.html
    assert resultat.html.count("Résumé de l'entreprise") >= 1


# ─── Robustesse ──────────────────────────────────────────────────────────────

@patch("agentAffichage.pipeline.generer_avec_outils")
def test_widget_invalide_laisse_le_markdown_intact(mock_generer):
    """Un tool call refusé en amont ne doit rien retirer à la réponse."""
    mock_generer.return_value = _generation(
        "Réponse complète et utile.",
        widgets=[],
        invalides=[ToolCallInvalide("afficher_chart", "arguments invalides : ...", "{}")],
    )

    resultat = genererAffichageAvecOutils("Question")

    assert "Réponse complète et utile." in resultat.html
    assert "widget:" not in resultat.html


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_echec_de_lappel_affiche_un_message_lisible(mock_generer, capsys):
    mock_generer.side_effect = RuntimeError("API indisponible")

    resultat = genererAffichageAvecOutils("Question")

    assert resultat.erreur == "API indisponible"
    assert "API indisponible" in resultat.html  # message visible, pas de carte vide
    assert "échec de l'appel" in capsys.readouterr().err


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_le_nouveau_flux_nappelle_jamais_la_selection(mock_generer):
    mock_generer.return_value = _generation("Texte.")

    with patch("agentAffichage.pipeline.selectionner_widget") as mock_selection:
        resultat = genererAffichageAvecOutils("Question")

    mock_selection.assert_not_called()
    assert resultat.resultat_selection is None
    assert resultat.resultat_generation is not None


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_console_de_generation_liste_appels_et_refus(mock_generer):
    mock_generer.return_value = _generation(
        "Texte.",
        widgets=[WidgetGenere("card", DonneesCard(titre="X", attributs=[]))],
        invalides=[ToolCallInvalide("afficher_chart", "outil mal renseigné", "{}")],
    )

    console = genererAffichageAvecOutils("Question").html.split("Console de génération")[1]

    assert "appelé" in console
    assert "ignoré" in console and "outil mal renseigné" in console


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_image_en_widget_nest_pas_affichee_deux_fois(mock_generer):
    """Le retrait de la référence d'image, déjà en place pour l'ancien flux,
    doit s'appliquer aussi ici."""
    url = "https://exemple.com/chat.jpg"
    mock_generer.return_value = _generation(
        f"Voici la photo : ![Un chat]({url})",
        [WidgetGenere("image", DonneesImage(url=url, alt="Un chat"))],
    )

    resultat = genererAffichageAvecOutils("Montre-moi un chat")

    assert resultat.html.count("<img") == 1


# ─── Comparaison ancien / nouveau ────────────────────────────────────────────

@patch("agentAffichage.pipeline.generer_avec_outils")
@patch("agentAffichage.pipeline.selectionner_widget")
def test_les_deux_flux_produisent_le_meme_rendu_pour_le_meme_widget(mock_selection, mock_generer):
    """Garantie centrale de la migration : à données de widget identiques, le
    HTML produit est le même — seule la façon de produire le widget change."""
    donnees = {"titre": "Apple Inc.", "attributs": [{"label": "PDG", "valeur": "Tim Cook"}]}
    texte = "Apple Inc. est dirigée par Tim Cook."

    mock_selection.return_value = _appel(ResultatSelection(candidats=[{
        "type": "card", "confidence": 0.95, "raison": "entité à plusieurs attributs",
        "donnees": donnees,
    }]))
    mock_generer.return_value = _generation(texte, [WidgetGenere("card", DonneesCard(**donnees))])

    html_ancien = genererAffichage(texte).html
    html_nouveau = genererAffichageAvecOutils(texte).html

    # Les consoles diffèrent (scores vs appels d'outils) : on compare la zone
    # de contenu, qui est ce que l'utilisateur voit réellement.
    contenu_ancien = html_ancien.split('<div class="content">')[1].split("<details>")[0]
    contenu_nouveau = html_nouveau.split('<div class="content">')[1].split("<details>")[0]
    assert contenu_ancien == contenu_nouveau
    assert "Tim Cook" in contenu_nouveau


@patch("agentAffichage.pipeline.generer_avec_outils")
@patch("agentAffichage.pipeline.selectionner_widget")
def test_les_deux_flux_sans_widget_produisent_le_meme_contenu(mock_selection, mock_generer):
    texte = "Il fait 15°C dehors."
    mock_selection.return_value = _appel(ResultatSelection(candidats=[]))
    mock_generer.return_value = _generation(texte)

    contenu_ancien = genererAffichage(texte).html.split('<div class="content">')[1].split("<details>")[0]
    contenu_nouveau = genererAffichageAvecOutils(texte).html.split('<div class="content">')[1].split("<details>")[0]

    assert contenu_ancien == contenu_nouveau


def test_les_deux_flux_partagent_la_meme_serialisation_de_widget():
    """_construire_blocs_widgets accepte les deux types de porteurs sans
    conversion intermédiaire (cf. le Protocol PorteurWidget)."""
    from agentAffichage.pipeline import _construire_blocs_widgets
    from agentAffichage.selection.schemas import WidgetCard

    donnees = DonneesCard(titre="X", attributs=[])
    ancien = WidgetCard(type="card", confidence=0.9, raison="test", donnees=donnees)
    nouveau = WidgetGenere("card", donnees)

    assert _construire_blocs_widgets([ancien]) == _construire_blocs_widgets([nouveau])
