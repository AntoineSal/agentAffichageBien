"""
Non-régression sur les bugs constatés les 20 et 21/08/2026 en testant la
nouvelle architecture dans le sandbox (voir bugs_new_architecture.txt) et en
simulant les sorties plausibles du modèle.
"""

import json
import re
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from agentAffichage.generation.generateur import convertir_tool_calls
from agentAffichage.generation.schemas import ResultatGeneration, WidgetGenere
from agentAffichage.pipeline import genererAffichageAvecOutils
from agentAffichage.rendu import registre
from agentAffichage.selection.schemas import (
    DonneesCard,
    DonneesChart,
    DonneesCode,
    DonneesStats,
    DonneesTable,
    DonneesTimeline,
)


def _generation(markdown, widgets=None):
    return ResultatGeneration(markdown=markdown, widgets=widgets or [], invalides=[])


# ─── Bug A : nombres refusés là où le schéma attend du texte ────────────────
# Pydantic v2 convertit "430" en float mais refuse 1957 en str. Un modèle qui
# remplit un widget envoie pourtant naturellement des nombres.

def test_stats_accepte_des_valeurs_numeriques():
    donnees = DonneesStats(indicateurs=[{"label": "Diamètre", "valeur": 12742}])
    assert donnees.indicateurs[0].valeur == "12742"


def test_timeline_accepte_une_annee_numerique():
    donnees = DonneesTimeline(evenements=[{"date": 1969, "titre": "Apollo 11"}])
    assert donnees.evenements[0].date == "1969"


def test_table_accepte_des_cellules_numeriques():
    donnees = DonneesTable(colonnes=["Pays", "Population"], lignes=[["Inde", 1428000000]])
    assert donnees.lignes[0][1] == "1428000000"


def test_card_accepte_un_attribut_numerique():
    donnees = DonneesCard(titre="Marie Curie", attributs=[{"label": "Naissance", "valeur": 1867}])
    assert donnees.attributs[0].valeur == "1867"


def test_chart_accepte_des_categories_numeriques():
    donnees = DonneesChart(
        type_graphique="ligne", categories=[2015, 2016], series=[{"valeurs": [1, 2]}]
    )
    assert donnees.categories == ["2015", "2016"]


def test_un_booleen_reste_refuse():
    """True n'est pas une valeur affichable : le laisser échouer est correct."""
    with pytest.raises(Exception):
        DonneesStats(indicateurs=[{"label": "Actif", "valeur": True}])


# ─── Bug B : le canvas du graphique s'écrasait à ~190x95 px ─────────────────

def test_le_canvas_est_seul_dans_un_conteneur_de_hauteur_fixe():
    """Exigence documentée de Chart.js en mode responsive : le parent du canvas
    doit lui être dédié et avoir une hauteur déterminée. Quand le titre
    partageait ce conteneur, le canvas se réduisait à ~190x95 px."""
    html = registre.graphique({
        "titre": "Un titre",
        "type_graphique": "ligne",
        "categories": ["a", "b"],
        "series": [{"valeurs": [1, 2]}],
    })
    conteneur = re.search(r'<div style="([^"]*)">\s*<canvas', html)
    assert conteneur is not None, "le canvas doit être seul dans son propre conteneur"
    style = conteneur.group(1)
    assert "position:relative" in style
    assert "height:280px" in style


def test_maintain_aspect_ratio_desactive():
    """Sans cette option, Chart.js ignore la hauteur imposée par le conteneur."""
    html = registre.graphique({
        "type_graphique": "ligne", "categories": ["a"], "series": [{"valeurs": [1]}],
    })
    config = json.loads(
        re.search(r'new Chart\(document\.getElementById\("chart-\w+"\), (\{.*?\})\);', html, re.DOTALL).group(1)
    )
    assert config["options"]["maintainAspectRatio"] is False


# ─── Bug C : le code apparaissait deux fois ─────────────────────────────────

@patch("agentAffichage.pipeline.generer_avec_outils")
def test_le_code_nest_pas_affiche_deux_fois(mock_generer):
    code = "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"
    mock_generer.return_value = _generation(
        f"Voici la fonction :\n\n```python\n{code}\n```\n\nElle est récursive.",
        [WidgetGenere("code", DonneesCode(code=code, langage="python"))],
    )

    html = genererAffichageAvecOutils("Fibonacci en Python").html
    contenu = html.split('<div class="content">')[1].split("<details>")[0]

    # Une seule occurrence du corps de la fonction dans la zone affichée.
    assert contenu.count("fibonacci(n-1)") == 1
    # Le texte d'accompagnement, lui, est conservé.
    assert "Elle est récursive." in contenu


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_un_autre_bloc_de_code_nest_pas_supprime(mock_generer):
    """Le retrait ne doit viser que le bloc repris par le widget."""
    code_widget = "print('widget')"
    mock_generer.return_value = _generation(
        f"Premier :\n\n```python\n{code_widget}\n```\n\nSecond :\n\n```python\nprint('autre')\n```",
        [WidgetGenere("code", DonneesCode(code=code_widget, langage="python"))],
    )

    contenu = genererAffichageAvecOutils("x").html.split('<div class="content">')[1].split("<details>")[0]

    assert "print('autre')" in contenu or "print(&#39;autre&#39;)" in contenu


# ─── Console : les données doivent être visibles pour diagnostiquer ─────────

@patch("agentAffichage.pipeline.generer_avec_outils")
def test_la_console_montre_les_donnees_envoyees_par_le_modele(mock_generer):
    """Sans les données, un widget qui s'affiche mal (URL d'image erronée) est
    indiagnosticable depuis l'interface."""
    from agentAffichage.selection.schemas import DonneesImage

    url = "https://exemple.com/photo-inexistante.png"
    mock_generer.return_value = _generation(
        "Voici la photo.", [WidgetGenere("image", DonneesImage(url=url))]
    )

    console = genererAffichageAvecOutils("Montre une photo").html.split("Console de génération")[1]

    assert url in console


# ─── Bug D (21/08) : graphique aux catégories manquantes ou décalées ────────
# Constaté deux fois : `categories: []` alors que 9 valeurs étaient fournies.
# Le renderer associe positionnellement categories[i] à valeurs[i] : sans
# étiquettes, le graphique s'affiche avec un axe muet.

def _tool_call(nom, arguments):
    """Reproduit la forme réelle : appel.function.name / appel.function.arguments."""
    return SimpleNamespace(function=SimpleNamespace(name=nom, arguments=arguments))


def test_chart_sans_categories_est_refuse():
    with pytest.raises(ValidationError):
        DonneesChart(type_graphique="ligne", categories=[], series=[{"valeurs": [1, 2, 3]}])


def test_chart_avec_plus_de_valeurs_que_de_categories_est_refuse():
    with pytest.raises(ValidationError) as erreur:
        DonneesChart(
            type_graphique="ligne",
            categories=["2020", "2021"],
            series=[{"valeurs": [1, 2, 3]}],
        )
    # Le message doit rester lisible dans la console de génération du sandbox.
    assert "catégorie" in str(erreur.value)


def test_chart_coherent_reste_accepte():
    donnees = DonneesChart(
        type_graphique="ligne", categories=["2020", "2021"], series=[{"valeurs": [1, 2]}]
    )
    assert len(donnees.categories) == len(donnees.series[0].valeurs)


def test_chart_a_plusieurs_series_verifie_chaque_serie():
    with pytest.raises(ValidationError):
        DonneesChart(
            type_graphique="ligne",
            categories=["2020", "2021"],
            series=[{"nom": "France", "valeurs": [1, 2]}, {"nom": "Italie", "valeurs": [3]}],
        )


def test_une_unite_qui_est_un_paragraphe_est_abandonnee_sans_perdre_le_graphique():
    """`unite` est un champ accessoire : le modèle l'a rempli avec un paragraphe
    entier de contexte et de sources. Rejeter tout le graphique pour ça serait
    disproportionné — la valeur aberrante est abandonnée, le graphique reste."""
    donnees = DonneesChart(
        type_graphique="ligne",
        categories=["2020"],
        series=[{"valeurs": [1]}],
        unite="Milliards de dollars US, source Banque mondiale, chiffres 2023 révisés",
    )
    assert donnees.unite is None


def test_une_unite_courte_est_conservee():
    donnees = DonneesChart(
        type_graphique="barres", categories=["a"], series=[{"valeurs": [1]}], unite="USD"
    )
    assert donnees.unite == "USD"


# ─── Bug E (21/08) : deux appels au même outil dans une réponse ─────────────

def test_le_meme_outil_appele_deux_fois_ne_donne_quun_widget():
    widgets, invalides = convertir_tool_calls([
        _tool_call("afficher_chart", {
            "type_graphique": "ligne", "categories": ["2020", "2021"], "series": [{"valeurs": [1, 2]}],
        }),
        _tool_call("afficher_chart", {
            "type_graphique": "barres", "categories": ["x", "y"], "series": [{"valeurs": [3, 4]}],
        }),
    ])

    assert [w.type for w in widgets] == ["chart"]
    assert widgets[0].donnees.type_graphique == "ligne"
    assert len(invalides) == 1
    assert "doublon" in invalides[0].erreur


def test_le_doublon_est_ecarte_apres_validation_pas_avant():
    """Cas réel : le modèle a envoyé un chart tronqué ET un chart complet. En
    validant avant de dédupliquer, l'appel malformé laisse sa place au suivant
    au lieu de faire perdre le widget."""
    widgets, invalides = convertir_tool_calls([
        _tool_call("afficher_chart", {
            "type_graphique": "ligne", "categories": [], "series": [{"valeurs": [1, 2]}],
        }),
        _tool_call("afficher_chart", {
            "type_graphique": "ligne", "categories": ["2020", "2021"], "series": [{"valeurs": [1, 2]}],
        }),
    ])

    assert [w.type for w in widgets] == ["chart"]
    assert widgets[0].donnees.categories == ["2020", "2021"]
    assert len(invalides) == 1


def test_deux_outils_differents_restent_autorises():
    """La déduplication est par type d'outil, pas globale : une card et une
    timeline sur la même réponse restent légitimes."""
    widgets, invalides = convertir_tool_calls([
        _tool_call("afficher_card", {"titre": "SpaceX", "attributs": []}),
        _tool_call("afficher_timeline", {"evenements": [{"date": "2002", "titre": "Fondation"}]}),
    ])

    assert [w.type for w in widgets] == ["card", "timeline"]
    assert invalides == []


# ─── Bug F (21/08) : code dupliqué quand le modèle reformule ────────────────
# `_remplacer_bloc_code` (alors `_retirer_bloc_code`) ne comparait qu'à l'identique (espaces ignorés) : un
# commentaire ajouté ou des espaces autour des opérateurs suffisaient à laisser
# passer le doublon.

_FIBONACCI = "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)"


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_un_bloc_legerement_reformule_est_quand_meme_retire(mock_generer):
    reformule = (
        "def fibonacci(n):\n    # Cas de base\n    if n <= 1:\n        return n\n"
        "    return fibonacci(n - 1) + fibonacci(n - 2)"
    )
    mock_generer.return_value = _generation(
        f"Voici la fonction :\n\n```python\n{reformule}\n```\n\nElle est récursive.",
        [WidgetGenere("code", DonneesCode(code=_FIBONACCI, langage="python"))],
    )

    contenu = genererAffichageAvecOutils("Fibonacci").html.split('<div class="content">')[1].split("<details>")[0]

    assert "fibonacci(n - 1)" not in contenu
    assert "Elle est récursive." in contenu


@patch("agentAffichage.pipeline.generer_avec_outils")
def test_une_fonction_differente_de_forme_voisine_nest_pas_retiree(mock_generer):
    """Garde-fou de la comparaison floue : deux fonctions récursives courtes se
    ressemblent beaucoup sans être le même code."""
    mock_generer.return_value = _generation(
        "Autre exemple :\n\n```python\ndef factorielle(n):\n    if n <= 1:\n        return 1\n"
        "    return n * factorielle(n-1)\n```",
        [WidgetGenere("code", DonneesCode(code=_FIBONACCI, langage="python"))],
    )

    contenu = genererAffichageAvecOutils("x").html.split('<div class="content">')[1].split("<details>")[0]

    assert "factorielle" in contenu


# ─── Bugs G/H (21/08) : règles de déclenchement dans le prompt/catalogue ────
# Ces bugs-là (sous-déclenchement de code/table, card utilisée pour comparer
# plusieurs entités, réponses trop longues) se corrigent par le texte envoyé au
# modèle, pas par du code : leur effet réel se mesure en test manuel. Ces tests
# ne vérifient donc que la présence des consignes — ils protègent d'un retrait
# accidentel, ils ne prouvent pas que le modèle les suit.

def test_le_prompt_interdit_dappeler_deux_fois_le_meme_outil():
    from agentAffichage.generation.prompt import construire_prompt_generation

    assert "deux fois le MÊME outil" in construire_prompt_generation()


def test_le_prompt_demande_de_la_concision():
    from agentAffichage.generation.prompt import construire_prompt_generation

    assert "Sois concis" in construire_prompt_generation()


def test_le_prompt_donne_des_exemples_de_cas_ou_loutil_est_attendu():
    """Levier principal contre le sous-déclenchement : la règle de retenue
    seule poussait le modèle à ne rien appeler même sur des cas francs."""
    from agentAffichage.generation.prompt import construire_prompt_generation

    prompt = construire_prompt_generation()
    assert "SQL" in prompt
    assert "Fibonacci" in prompt


def test_le_catalogue_deconseille_la_card_pour_comparer_des_entites():
    from agentAffichage.selection.catalogue import CATALOGUE

    card = next(w for w in CATALOGUE if w.cle == "card")
    assert "PLUSIEURS entités" in card.ne_pas_utiliser_quand


def test_le_catalogue_reconnait_une_requete_sql_comme_du_code():
    from agentAffichage.selection.catalogue import CATALOGUE

    code = next(w for w in CATALOGUE if w.cle == "code")
    assert "SQL" in code.utiliser_quand
