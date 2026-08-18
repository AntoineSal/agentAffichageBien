"""
Les 8 fonctions de rendu génériques (registre.py) : rendent ce qui est fourni,
n'affichent rien pour ce qui est absent (même convention que carte_meteo), et
ne plantent jamais sur une entrée vide ou partielle.
"""

from agentAffichage.rendu import registre


def test_image_rend_url_et_legende():
    html = registre.image({"url": "https://exemple.com/paris.jpg", "legende": "Paris"})
    assert 'src="https://exemple.com/paris.jpg"' in html
    assert "Paris" in html


def test_image_vide_sans_url_ne_rend_rien():
    assert registre.image({}) == ""


def test_tableau_rend_colonnes_et_lignes():
    html = registre.tableau({"colonnes": ["Ville", "Population"], "lignes": [["Paris", "2,1M"]]})
    assert "Ville" in html and "Paris" in html and "2,1M" in html


def test_tableau_sans_colonnes_ne_rend_rien():
    assert registre.tableau({}) == ""


def test_code_rend_le_contenu_et_le_langage():
    html = registre.code({"code": "print('hi')", "langage": "python"})
    assert "print(&#x27;hi&#x27;)" in html or "print(" in html
    assert "language-python" in html


def test_code_sans_contenu_ne_rend_rien():
    assert registre.code({}) == ""


def test_fichier_rend_nom_et_icone_pdf():
    html = registre.fichier({"url": "https://exemple.com/rapport.pdf"})
    assert "rapport.pdf" in html
    assert "📄" in html


def test_fichier_sans_url_ne_rend_rien():
    assert registre.fichier({}) == ""


def test_carte_rend_titre_et_attributs():
    html = registre.carte({
        "titre": "Apple Inc.",
        "attributs": [{"label": "Fondation", "valeur": "1976"}, {"label": "PDG", "valeur": "Tim Cook"}],
    })
    assert "Apple Inc." in html
    assert "Fondation" in html and "1976" in html
    assert "PDG" in html and "Tim Cook" in html


def test_carte_sans_titre_ne_rend_rien():
    assert registre.carte({"attributs": [{"label": "X", "valeur": "Y"}]}) == ""


def test_carte_sans_attributs_rend_juste_le_titre():
    html = registre.carte({"titre": "Paris"})
    assert "Paris" in html


def test_graphique_rend_la_config_chartjs():
    html = registre.graphique({
        "type_graphique": "ligne",
        "categories": ["Lun", "Mar"],
        "series": [{"valeurs": [15, 18]}],
    })
    assert "new Chart(" in html
    assert '"type": "line"' in html


def test_graphique_sans_series_ne_rend_rien():
    assert registre.graphique({"type_graphique": "ligne"}) == ""


def test_statistiques_rend_les_indicateurs():
    html = registre.statistiques({"indicateurs": [{"label": "CA", "valeur": "420 M€", "tendance": "+12%"}]})
    assert "CA" in html and "420 M€" in html and "+12%" in html


def test_statistiques_indicateur_sans_tendance_ne_montre_pas_de_tendance():
    html = registre.statistiques({"indicateurs": [{"label": "CA", "valeur": "420 M€"}]})
    assert "420 M€" in html
    assert "%" not in html


def test_statistiques_vide_ne_rend_rien():
    assert registre.statistiques({}) == ""


def test_chronologie_rend_les_evenements_dans_lordre_fourni():
    html = registre.chronologie({"evenements": [
        {"date": "1976", "titre": "Fondation"},
        {"date": "2007", "titre": "iPhone"},
    ]})
    assert html.index("1976") < html.index("2007")


def test_chronologie_ignore_un_evenement_sans_date():
    html = registre.chronologie({"evenements": [
        {"date": "1976", "titre": "Fondation"},
        {"titre": "sans date"},
    ]})
    assert "Fondation" in html
    assert "sans date" not in html


def test_chronologie_vide_ne_rend_rien():
    assert registre.chronologie({}) == ""
