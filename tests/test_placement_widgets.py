"""
Placement des widgets dans le corps du message (phase 1 de
FEUILLE_DE_ROUTE_WIDGETS_INTEGRES.md, implémentée le 24/08/2026).

Jusqu'ici tous les blocs étaient concaténés en fin de réponse. Deux règles les
remplacent :

1. quand le texte référence déjà le contenu (image, code), le widget prend la
   place de cette référence ;
2. sinon, la position par défaut déclarée par le type dans
   `selection/catalogue.py` s'applique (début ou fin).

Tout est simulé — aucun appel réseau, aucune clé requise.
"""

from unittest.mock import patch

from agentAffichage.generation.schemas import ResultatGeneration, WidgetGenere
from agentAffichage.pipeline import _annoter_texte, genererAffichage, genererAffichageAvecOutils
from agentAffichage.metriques import Metriques
from agentAffichage.selection.catalogue import DEBUT, FIN, POSITION_PAR_CLE
from agentAffichage.selection.schemas import (
    DonneesCard,
    DonneesChart,
    DonneesCode,
    DonneesImage,
    DonneesStats,
    ResultatSelection,
)
from agentAffichage.selection.selecteur import AppelSelection

URL = "https://upload.wikimedia.org/wikipedia/commons/6/63/logo.png"

CODE = "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"


def _ordre(texte, *reperes):
    """Repères présents, classés par position d'apparition dans le texte."""
    presents = [r for r in reperes if r in texte]
    return sorted(presents, key=texte.find)


def _widget(cle, donnees):
    return WidgetGenere(cle, donnees)


_CARD = _widget("card", DonneesCard(titre="Marie Curie", attributs=[{"label": "Née", "valeur": "1867"}]))
_STATS = _widget("stats", DonneesStats(indicateurs=[{"label": "Prix Nobel", "valeur": "2"}]))
_CHART = _widget("chart", DonneesChart(
    type_graphique="ligne", categories=["1903", "1911"], series=[{"valeurs": [1, 2]}],
))
_IMAGE = _widget("image", DonneesImage(url=URL, legende="Logo"))
_CODE = _widget("code", DonneesCode(code=CODE, langage="python"))


# ─── Positions par défaut déclarées au catalogue ────────────────────────────

def test_les_widgets_qui_repondent_a_la_question_sont_en_tete():
    """card et stats RÉPONDENT à la question : le texte les commente ensuite."""
    assert POSITION_PAR_CLE["card"] == DEBUT
    assert POSITION_PAR_CLE["stats"] == DEBUT


def test_les_widgets_qui_appuient_une_demonstration_sont_en_fin():
    for cle in ("chart", "table", "timeline", "file", "code"):
        assert POSITION_PAR_CLE[cle] == FIN, cle


def test_un_type_hors_catalogue_retombe_sur_la_fin():
    """Les widgets de rendu non proposés par la sélection ("weather", "titre"...)
    n'ont pas d'entrée : ils ne doivent pas faire planter le placement."""
    autre = _widget("weather", DonneesCard(titre="Paris", attributs=[]))
    resultat = _annoter_texte("Il fait beau.", [autre])

    assert _ordre(resultat, "Il fait beau.", "widget:weather") == ["Il fait beau.", "widget:weather"]


# ─── Placement par défaut ───────────────────────────────────────────────────

def test_la_card_passe_avant_le_texte():
    resultat = _annoter_texte("Marie Curie est une physicienne.", [_CARD])

    assert _ordre(resultat, "widget:card", "Marie Curie est") == ["widget:card", "Marie Curie est"]


def test_le_graphique_reste_apres_le_texte():
    resultat = _annoter_texte("Ses prix se répartissent ainsi.", [_CHART])

    assert _ordre(resultat, "Ses prix", "widget:chart") == ["Ses prix", "widget:chart"]


def test_card_et_graphique_encadrent_le_texte():
    """Le cas visé : le widget qui résume ouvre le message, celui qui appuie le
    referme — le texte n'est plus suivi d'un bloc de widgets détachés."""
    texte = "Marie Curie est une physicienne polonaise.\n\nElle a reçu deux prix Nobel."
    resultat = _annoter_texte(texte, [_CHART, _CARD])

    assert _ordre(resultat, "widget:card", "physicienne polonaise", "deux prix Nobel", "widget:chart") == [
        "widget:card", "physicienne polonaise", "deux prix Nobel", "widget:chart",
    ]


def test_l_ordre_d_appel_du_modele_est_conserve_dans_un_meme_emplacement():
    resultat = _annoter_texte("Texte.", [_STATS, _CARD])

    assert _ordre(resultat, "widget:stats", "widget:card") == ["widget:stats", "widget:card"]


def test_sans_widget_le_texte_est_inchange():
    assert _annoter_texte("Bonjour, comment vas-tu ?", []) == "Bonjour, comment vas-tu ?"


# ─── Substitution en place : image ──────────────────────────────────────────

def test_l_image_prend_la_place_de_sa_reference_markdown():
    texte = f"Voici le logo :\n\n![Logo]({URL})\n\nIl date de 2010."
    resultat = _annoter_texte(texte, [_IMAGE])

    assert _ordre(resultat, "Voici le logo", "widget:image", "Il date de 2010") == [
        "Voici le logo", "widget:image", "Il date de 2010",
    ]
    assert "![Logo]" not in resultat


def test_l_image_prend_la_place_d_une_url_nue():
    texte = f"Le logo est ici :\n\n{URL}\n\nFin."
    resultat = _annoter_texte(texte, [_IMAGE])

    assert _ordre(resultat, "Le logo est ici", "widget:image", "Fin.") == [
        "Le logo est ici", "widget:image", "Fin.",
    ]


def test_une_reference_au_fil_d_une_phrase_ne_coupe_pas_la_phrase():
    """Un bloc widget inséré en plein paragraphe serait absorbé par le parser
    Markdown : la phrase est conservée, amputée de la référence, et le widget
    posé juste après elle."""
    resultat = _annoter_texte(f"Le logo ![Logo]({URL}) est libre de droits.", [_IMAGE])

    assert "est libre de droits." in resultat
    assert _ordre(resultat, "est libre de droits.", "widget:image") == [
        "est libre de droits.", "widget:image",
    ]


def test_une_url_citee_deux_fois_ne_laisse_pas_de_doublon():
    texte = f"![Logo]({URL})\n\nSource : {URL}"
    resultat = _annoter_texte(texte, [_IMAGE])

    # L'URL ne subsiste que dans le JSON du bloc widget.
    assert resultat.count(URL) == 1


def test_une_image_non_referencee_retombe_sur_la_position_par_defaut():
    """Le modèle a appelé l'outil sans que sa réponse mentionne l'URL."""
    resultat = _annoter_texte("Voici une photo de la tour Eiffel.", [_IMAGE])

    assert _ordre(resultat, "widget:image", "Voici une photo") == [
        "widget:image", "Voici une photo",
    ]


# ─── Substitution en place : code ───────────────────────────────────────────

def test_le_code_prend_la_place_de_son_bloc_markdown():
    texte = f"Voici la fonction :\n\n```python\n{CODE}\n```\n\nElle est récursive."
    resultat = _annoter_texte(texte, [_CODE])

    assert _ordre(resultat, "Voici la fonction", "widget:code", "Elle est récursive") == [
        "Voici la fonction", "widget:code", "Elle est récursive",
    ]
    assert "```python" not in resultat


def test_un_bloc_reformule_prend_quand_meme_la_place():
    """Prolonge le correctif du 21/08 : la comparaison floue sert maintenant à
    placer le widget, pas seulement à retirer le doublon."""
    reformule = (
        "def fibonacci(n):\n    # Cas de base\n    if n <= 1:\n        return n\n"
        "    return fibonacci(n - 1) + fibonacci(n - 2)"
    )
    texte = f"Voici la fonction :\n\n```python\n{reformule}\n```\n\nElle est récursive."
    resultat = _annoter_texte(texte, [_CODE])

    assert "fibonacci(n - 1)" not in resultat
    assert _ordre(resultat, "Voici la fonction", "widget:code", "Elle est récursive") == [
        "Voici la fonction", "widget:code", "Elle est récursive",
    ]


def test_un_code_absent_du_texte_retombe_en_fin():
    resultat = _annoter_texte("Voici comment faire.", [_CODE])

    assert _ordre(resultat, "Voici comment faire", "widget:code") == [
        "Voici comment faire", "widget:code",
    ]


def test_une_autre_fonction_nest_pas_remplacee():
    autre = "def factorielle(n):\n    if n <= 1:\n        return 1\n    return n * factorielle(n-1)"
    resultat = _annoter_texte(f"Exemple :\n\n```python\n{autre}\n```", [_CODE])

    assert "factorielle" in resultat


# ─── Sécurité : ne jamais insérer dans un bloc de code ──────────────────────

def test_une_url_citee_dans_un_bloc_de_code_nest_pas_substituee():
    """`_WIDGET_BLOCK_RE` du renderer n'est pas conscient des fences : un bloc
    widget posé au milieu d'un bloc de code casserait ce bloc ET afficherait le
    widget au mauvais endroit."""
    texte = f"Exemple de configuration :\n\n```yaml\nlogo: {URL}\n```\n\nVoilà."
    resultat = _annoter_texte(texte, [_IMAGE])

    assert f"logo: {URL}" in resultat          # le bloc yaml est intact
    assert resultat.startswith("```widget:image")  # repli sur la position par défaut


def test_les_blocs_widgets_sont_separes_par_des_lignes_vides():
    """Sans ligne vide, le parser Markdown absorbe le bloc dans le paragraphe
    voisin (l'extension nl2br est active)."""
    resultat = _annoter_texte("Un paragraphe.", [_CARD, _CHART])

    assert "\n\n```widget:chart" in resultat
    assert "```\n\nUn paragraphe." in resultat


# ─── Rendu final : l'ordre HTML suit l'ordre des blocs ──────────────────────

@patch("agentAffichage.pipeline.generer_avec_outils")
def test_le_html_final_place_la_card_avant_le_texte(mock_generer):
    mock_generer.return_value = ResultatGeneration(
        markdown="Marie Curie est une physicienne polonaise.\n\nElle a reçu deux prix Nobel.",
        widgets=[_CHART, _CARD],
        invalides=[],
    )

    contenu = genererAffichageAvecOutils("Marie Curie ?").html.split('<div class="content">')[1]
    contenu = contenu.split("<details")[0]

    assert _ordre(contenu, "Marie Curie</", "physicienne polonaise", "deux prix Nobel", "<canvas") == [
        "Marie Curie</", "physicienne polonaise", "deux prix Nobel", "<canvas",
    ]


# ─── Les deux flux restent alignés ──────────────────────────────────────────

@patch("agentAffichage.pipeline.generer_avec_outils")
@patch("agentAffichage.pipeline.selectionner_widget")
def test_l_ancien_flux_place_les_widgets_de_la_meme_facon(mock_selection, mock_generer):
    """`_annoter_texte` est partagée : l'ancien pipeline gagne le même placement
    sans que `selection/` soit modifié."""
    donnees = {"titre": "Apple Inc.", "attributs": [{"label": "PDG", "valeur": "Tim Cook"}]}
    texte = "Apple Inc. est dirigée par Tim Cook."

    mock_selection.return_value = AppelSelection(
        ResultatSelection(candidats=[{
            "type": "card", "confidence": 0.95, "raison": "entité à plusieurs attributs",
            "donnees": donnees,
        }]),
        Metriques(),
    )
    mock_generer.return_value = ResultatGeneration(
        markdown=texte, widgets=[_widget("card", DonneesCard(**donnees))], invalides=[]
    )

    decoupe = lambda html: html.split('<div class="content">')[1].split("<details>")[0]
    contenu_ancien = decoupe(genererAffichage(texte).html)
    contenu_nouveau = decoupe(genererAffichageAvecOutils(texte).html)

    assert contenu_ancien == contenu_nouveau
    assert contenu_ancien.find("Tim Cook") < contenu_ancien.find("est dirigée par")
