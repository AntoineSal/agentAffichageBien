"""
pipeline.py : orchestration sélection -> filtrage par seuil de confiance ->
retrait de la référence image en double -> rendu (0, 1 ou plusieurs widgets)
-> console de debug, et fallback en cas d'échec. selectionner_widget est
simulée partout ici — aucun appel réseau.
"""

from unittest.mock import patch

from agentAffichage.metriques import Metriques
from agentAffichage.pipeline import genererAffichage
from agentAffichage.selection.confiance import SEUIL_AFFICHAGE
from agentAffichage.selection.schemas import ResultatSelection
from agentAffichage.selection.selecteur import AppelSelection


def _candidat(type_, confidence, raison="test", **donnees):
    return {"type": type_, "confidence": confidence, "raison": raison, "donnees": donnees}


def _appel(resultat, metriques=None):
    """Reproduit la forme réelle de selectionner_widget() : (resultat, métriques)."""
    return AppelSelection(resultat, metriques or Metriques())


@patch("agentAffichage.pipeline.selectionner_widget")
def test_candidat_au_dessus_du_seuil_est_rendu(mock_selectionner):
    mock_selectionner.return_value = _appel(ResultatSelection(candidats=[
        _candidat("stats", SEUIL_AFFICHAGE + 0.1, indicateurs=[{"label": "CA", "valeur": "420 M€"}]),
    ]))

    resultat = genererAffichage("Le chiffre d'affaires est de 420 M€.")

    assert "420 M" in resultat.html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_candidat_sous_le_seuil_nest_pas_rendu(mock_selectionner):
    mock_selectionner.return_value = _appel(ResultatSelection(candidats=[
        _candidat("stats", SEUIL_AFFICHAGE - 0.1, indicateurs=[{"label": "CA", "valeur": "420 M€"}]),
    ]))

    resultat = genererAffichage("Bonjour, comment vas-tu ?")

    # Le texte source reste affiché (repli), mais aucune carte de stats n'est
    # injectée : la ligne "CA" du candidat rejeté ne doit apparaître nulle part.
    assert "Bonjour" in resultat.html
    assert "widget:" not in resultat.html
    assert "CA" not in resultat.html.split("Console de sélection")[0]


@patch("agentAffichage.pipeline.selectionner_widget")
def test_seuls_les_candidats_retenus_sont_rendus_parmi_plusieurs(mock_selectionner):
    mock_selectionner.return_value = _appel(ResultatSelection(candidats=[
        _candidat("card", 0.91, titre="Apple Inc.", attributs=[{"label": "PDG", "valeur": "Tim Cook"}]),
        _candidat("stats", 0.42, indicateurs=[{"label": "Fondation", "valeur": "1976"}]),
    ]))

    resultat = genererAffichage("Petit résumé d'Apple.")

    assert "Apple Inc." in resultat.html and "Tim Cook" in resultat.html
    assert "widget:stats" not in resultat.html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_aucun_candidat_rend_juste_le_texte(mock_selectionner):
    mock_selectionner.return_value = _appel(ResultatSelection())

    resultat = genererAffichage("Bonjour, comment vas-tu ?")

    assert "Bonjour" in resultat.html
    assert "widget:" not in resultat.html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_echec_de_la_selection_retombe_sur_le_texte_brut(mock_selectionner, capsys):
    mock_selectionner.side_effect = RuntimeError("panne simulée")

    resultat = genererAffichage("Bonjour, comment vas-tu ?")

    assert "Bonjour" in resultat.html
    assert "widget:" not in resultat.html
    assert "panne simulée" in capsys.readouterr().err


@patch("agentAffichage.pipeline.selectionner_widget")
def test_cle_api_transmise_a_la_selection(mock_selectionner):
    mock_selectionner.return_value = _appel(ResultatSelection())

    genererAffichage("Texte quelconque.", api_key="cle-de-test")

    args, kwargs = mock_selectionner.call_args
    assert args[0] == "Texte quelconque."
    assert kwargs["api_key"] == "cle-de-test"


# ─── ResultatAffichage : visibilité pour la console de debug ────────────────

@patch("agentAffichage.pipeline.selectionner_widget")
def test_resultat_selection_expose_tous_les_candidats(mock_selectionner):
    r = ResultatSelection(candidats=[
        _candidat("card", 0.91, titre="Apple Inc.", attributs=[]),
        _candidat("stats", 0.42, indicateurs=[]),
    ])
    mock_selectionner.return_value = _appel(r)

    resultat = genererAffichage("Petit résumé d'Apple.")

    assert resultat.resultat_selection is r
    assert len(resultat.resultat_selection.candidats) == 2
    assert resultat.erreur is None


@patch("agentAffichage.pipeline.selectionner_widget")
def test_echec_expose_erreur_et_resultat_selection_none(mock_selectionner):
    mock_selectionner.side_effect = RuntimeError("panne simulée")

    resultat = genererAffichage("Bonjour.")

    assert resultat.resultat_selection is None
    assert resultat.erreur == "panne simulée"


@patch("agentAffichage.pipeline.selectionner_widget")
def test_console_liste_les_candidats_retenus_et_rejetes(mock_selectionner):
    mock_selectionner.return_value = _appel(ResultatSelection(candidats=[
        _candidat("card", 0.91, raison="entité avec plusieurs attributs", titre="Apple Inc.", attributs=[]),
        _candidat("stats", 0.42, raison="valeur isolée", indicateurs=[]),
    ]))

    resultat = genererAffichage("Petit résumé d'Apple.")
    console = resultat.html.split("Console de sélection")[1]

    assert "91%" in console and "retenu" in console and "entité avec plusieurs attributs" in console
    assert "42%" in console and "rejeté" in console and "valeur isolée" in console


@patch("agentAffichage.pipeline.selectionner_widget")
def test_console_signale_lechec_de_selection(mock_selectionner):
    mock_selectionner.side_effect = RuntimeError("panne simulée")

    resultat = genererAffichage("Bonjour.")

    assert "panne simulée" in resultat.html.split("Console de sélection")[1]


# ─── Widget image : exception, la référence brute disparaît du texte ────────

@patch("agentAffichage.pipeline.selectionner_widget")
def test_image_retenue_retire_la_syntaxe_markdown_du_texte_source(mock_selectionner):
    url = "https://exemple.com/chat.jpg"
    mock_selectionner.return_value = _appel(ResultatSelection(candidats=[
        _candidat("image", 0.9, url=url, alt="Un chat"),
    ]))

    resultat = genererAffichage(f"Voici la photo : ![Un chat]({url})")

    # Une seule balise <img> (celle du widget) ; le lien Markdown d'origine
    # a disparu du texte source affiché.
    assert resultat.html.count("<img") == 1
    assert f"![Un chat]({url})" not in resultat.html


@patch("agentAffichage.pipeline.selectionner_widget")
def test_image_retenue_retire_lurl_nue_du_texte_source(mock_selectionner):
    url = "https://exemple.com/chat.jpg"
    mock_selectionner.return_value = _appel(ResultatSelection(candidats=[
        _candidat("image", 0.9, url=url),
    ]))

    resultat = genererAffichage(f"Voici la photo : {url}")

    assert resultat.html.count("<img") == 1
    # Le texte introductif reste visible ; l'URL nue ne doit plus apparaître
    # dans la zone de contenu affichée (elle réapparaît légitimement plus bas
    # dans "voir le texte source", qui montre le texte annoté au complet —
    # ce n'est pas la duplication visible qu'on corrige ici).
    contenu_visible = resultat.html.split('<div class="content">')[1].split("<details>")[0]
    assert "Voici la photo" in contenu_visible
    assert url not in contenu_visible.split("<img")[0]


@patch("agentAffichage.pipeline.selectionner_widget")
def test_autres_widgets_ne_retirent_rien_du_texte_source(mock_selectionner):
    """L'exception est propre à image (et code) : un lien de fichier retenu
    doit rester visible dans le texte en plus du widget (le texte doit rester
    compréhensible seul)."""
    url = "https://exemple.com/rapport.pdf"
    mock_selectionner.return_value = _appel(ResultatSelection(candidats=[
        _candidat("file", 0.9, url=url, nom="rapport.pdf"),
    ]))

    resultat = genererAffichage(f"Voici le rapport : [Télécharger]({url})")

    contenu_avant_details = resultat.html.split("<details>")[0]
    assert url in contenu_avant_details


# ─── Métriques exposées dans la console ──────────────────────────────────────

@patch("agentAffichage.pipeline.selectionner_widget")
def test_la_console_affiche_le_temps_et_les_tokens(mock_selectionner):
    mock_selectionner.return_value = _appel(
        ResultatSelection(),
        Metriques(temps_appel_ms=842.0, tokens_prompt=310, tokens_completion=90, tokens_total=400),
    )

    console = genererAffichage("Bonjour.").html.split("Console de sélection")[1]

    assert "842" in console
    assert "310+90=400 tokens" in console


@patch("agentAffichage.pipeline.selectionner_widget")
def test_la_console_signale_les_tokens_indisponibles(mock_selectionner):
    mock_selectionner.return_value = _appel(ResultatSelection())  # Metriques() par défaut, tokens=None

    console = genererAffichage("Bonjour.").html.split("Console de sélection")[1]

    assert "tokens indisponibles" in console
