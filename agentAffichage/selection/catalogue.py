"""
Catalogue déclaratif des 8 widgets connus par la sélection — la liste fermée
imposée par la spec (IMAGE, TABLE, CODE, FILE, CARD, CHART, STATS, TIMELINE).
Ne pas ajouter de widget en dehors de cette liste sans demande explicite.

Ajouter un widget ici (et son schéma dans schemas.py, sa fonction de rendu dans
rendu/registre.py, son entrée de dispatch dans rendu/afficheur.py) suffit à
l'intégrer partout : le prompt de sélection (voir prompt.py) se génère
automatiquement depuis cette liste, sans rien modifier d'autre.
"""

from dataclasses import dataclass
from typing import Type

from pydantic import BaseModel

from .schemas import (
    DonneesCard,
    DonneesChart,
    DonneesCode,
    DonneesFichier,
    DonneesImage,
    DonneesStats,
    DonneesTable,
    DonneesTimeline,
)


# Emplacements possibles d'un widget dans la réponse. Volontairement grossiers :
# "début" et "fin" suffisent à tout ce qui a été demandé, et se décident sans
# rien demander au modèle (voir FEUILLE_DE_ROUTE_WIDGETS_INTEGRES.md, phase 1).
DEBUT = "debut"
FIN = "fin"


@dataclass(frozen=True)
class DescripteurWidget:
    cle: str
    objectif: str
    utiliser_quand: str
    ne_pas_utiliser_quand: str
    schema: Type[BaseModel]
    # Où poser le widget quand le texte ne dit pas lui-même où il va. Un widget
    # qui RÉPOND à la question se place avant le texte qui la développe ; un
    # widget qui APPUIE une démonstration déjà écrite se place après elle.
    # `image` et `code` sont des cas à part : quand le texte les référence
    # explicitement, ils prennent la place de cette référence et cette valeur
    # n'est utilisée qu'en repli (voir pipeline._annoter_texte).
    position: str = FIN


CATALOGUE = [
    DescripteurWidget(
        cle="image",
        objectif="Afficher une image déjà référencée dans le texte comme composant visuel dédié.",
        utiliser_quand=(
            'Une image Markdown (![description](url)) ou une URL d\'image directe est '
            "explicitement présente dans le texte."
        ),
        ne_pas_utiliser_quand=(
            'Le texte mentionne une image sans fournir d\'URL utilisable (ex: "Voici une '
            'photo de Paris." sans lien). N\'invente jamais d\'URL.'
        ),
        schema=DonneesImage,
        # Repli seulement : normalement l'image prend la place de la référence
        # présente dans le texte.
        position=DEBUT,
    ),
    DescripteurWidget(
        cle="table",
        objectif="Afficher des données tabulaires sous forme de tableau interactif amélioré (tri, filtre, recherche, pagination, colonnes fixes).",
        utiliser_quand=(
            "Plusieurs entités (au moins 4) sont comparées sur plusieurs critères (au moins 3), "
            "ou les données comportent des valeurs numériques que l'utilisateur voudrait "
            "raisonnablement trier, filtrer ou rechercher. Exemple typique qui justifie ce "
            "widget : comparer 5 langages de programmation selon leur typage, leur vitesse, "
            "leur courbe d'apprentissage et leur usage — 5 lignes x 4 colonnes se lisent "
            "nettement mieux dans un tableau triable que dans de la prose."
        ),
        ne_pas_utiliser_quand=(
            "Le jeu de données est petit (moins de 4 lignes OU moins de 3 colonnes) : "
            'ex. "les deux plus grands océans et leur superficie" se dit très bien en une '
            "phrase ou un mini-tableau Markdown. La présence d'un tableau Markdown ne "
            "déclenche PAS automatiquement ce widget."
        ),
        schema=DonneesTable,
    ),
    DescripteurWidget(
        cle="code",
        objectif="Afficher du code source dans une visionneuse améliorée (coloration syntaxique, langage, numéros de ligne).",
        utiliser_quand=(
            "Le texte contient un bloc de code source d'au moins 2 lignes formant un ensemble "
            "autonome : une fonction, une classe, un script, une requête SQL, un fichier de "
            "configuration. C'est le cas dès qu'on demande d'écrire, de montrer ou de donner "
            'un exemple de code (ex: "écris une fonction Python qui calcule Fibonacci", '
            '"donne un exemple de requête SQL") — ce sont des cas typiques, pas des cas limites.'
        ),
        ne_pas_utiliser_quand=(
            "Un court fragment de code en ligne (inline), cité au fil d'une explication et tenant "
            'sur une ligne (ex: "la fonction len() renvoie la longueur, comme dans len(ma_liste)"). '
            "Le widget doit rester proportionnel à la quantité et à l'importance du code."
        ),
        schema=DonneesCode,
    ),
    DescripteurWidget(
        cle="file",
        objectif="Afficher un fichier téléchargeable référencé par le texte (PDF, DOCX, XLSX, PPTX, CSV, ZIP, TXT...) comme composant dédié.",
        utiliser_quand=(
            'Une URL de fichier réellement utilisable est présente (ex: "[Télécharger le '
            'rapport](https://exemple.com/rapport.pdf)").'
        ),
        ne_pas_utiliser_quand=(
            'Le texte parle d\'un document sans lien utilisable (ex: "Le rapport annuel fait '
            '120 pages."). N\'invente jamais de fichier.'
        ),
        schema=DonneesFichier,
    ),
    DescripteurWidget(
        cle="card",
        objectif="Présenter une entité clairement identifiable (personne, entreprise, produit, lieu, livre, film, organisation...) sous forme structurée et compacte.",
        utiliser_quand=(
            "Le texte décrit une entité avec PLUSIEURS attributs distincts "
            '(ex: "Apple Inc. a été fondée en 1976. Son siège social est à Cupertino. Son PDG '
            'est Tim Cook." → titre + 2-3 attributs).'
        ),
        ne_pas_utiliser_quand=(
            'Une phrase triviale ne contenant qu\'une seule information (ex: "Paris est la '
            'capitale de la France." ne justifie pas une card). Surtout : PLUSIEURS entités '
            "comparées entre elles sur les mêmes critères — une card décrit UNE seule entité. "
            'Comparer la démographie de la France, l\'Allemagne et l\'Italie n\'est PAS une card : '
            "c'est un tableau (ou un graphique si les valeurs évoluent dans le temps). "
            "N'invente jamais un attribut manquant — n'affiche que ce que le texte soutient."
        ),
        schema=DonneesCard,
        # Une card résume l'entité dont parle la réponse : elle se lit avant le
        # texte qui la détaille, pas après.
        position=DEBUT,
    ),
    DescripteurWidget(
        cle="chart",
        objectif="Représenter visuellement une évolution temporelle, une comparaison entre plusieurs entités, ou une distribution, quand un graphique se comprend nettement mieux qu'une phrase.",
        utiliser_quand=(
            'Une série de valeurs comparables (temporelle ou catégorielle) est présente '
            '(ex: "100 M€ en 2021, 150 M€ en 2022, 180 M€ en 2023, 210 M€ en 2024" → ligne ; '
            '"Paris 2,1M, Marseille 0,9M, Lyon 0,5M" → barres). Choisis type_graphique parmi '
            "ligne (évolution temporelle), barres (comparaison catégorielle), secteurs "
            "(part du tout, seulement si vraiment pertinent), nuage_points (deux variables "
            "numériques comparées)."
        ),
        ne_pas_utiliser_quand=(
            'Un seul nombre isolé (ex: "La population de Paris est d\'environ 2,1 millions '
            'd\'habitants." ne justifie PAS un graphique) ou un jeu de données trop petit pour '
            "bénéficier d'une visualisation. N'invente jamais un point de donnée manquant."
        ),
        schema=DonneesChart,
    ),
    DescripteurWidget(
        cle="stats",
        objectif="Mettre en avant un petit nombre d'indicateurs numériques clés (KPI, mesures financières, scores, comptages...) de façon visuellement proéminente et facile à balayer du regard.",
        utiliser_quand=(
            'Un ensemble significatif de mesures clés est présent (ex: "Chiffre d\'affaires : '
            '420 M€. Croissance : +12%. Marge : 24%. Employés : 4 200." → 4 indicateurs).'
        ),
        ne_pas_utiliser_quand=(
            "Une valeur numérique unique et insignifiante, ou une phrase déjà simple et claire "
            "que la card statistique ne ferait que dupliquer. N'invente jamais de valeur, "
            "d'unité, de comparaison ou de tendance."
        ),
        schema=DonneesStats,
        # Même rôle que la card : quand on demande "les chiffres clés de X", les
        # indicateurs SONT la réponse — le texte les commente ensuite.
        position=DEBUT,
    ),
    DescripteurWidget(
        cle="timeline",
        objectif="Afficher plusieurs événements distincts organisés chronologiquement (histoire, biographie, jalons de projet, séquence de procédure...).",
        utiliser_quand=(
            'Le texte décrit une séquence d\'événements datés formant une progression '
            'significative (ex: "1976 : fondation d\'Apple. 1984 : Macintosh. 2007 : iPhone." '
            "→ 3 événements)."
        ),
        ne_pas_utiliser_quand=(
            "Une seule date/événement, ou plusieurs dates qui ne forment pas une séquence "
            "chronologique significative. N'invente jamais de date ou d'événement."
        ),
        schema=DonneesTimeline,
    ),
]


# Clé de widget -> position par défaut. Un type absent de cette table (widgets
# de rendu non proposés par la sélection : "weather", "titre", "paragraphe",
# "liste") retombe sur FIN.
POSITION_PAR_CLE = {w.cle: w.position for w in CATALOGUE}
