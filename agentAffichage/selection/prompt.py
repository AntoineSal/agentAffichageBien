"""
Construit le prompt système de l'appel Mistral de sélection à partir du
catalogue de widgets (catalogue.py). Ajouter un widget au catalogue met à jour
le prompt automatiquement, sans modifier ce fichier.
"""

from .catalogue import CATALOGUE

_REGLES_EXTRACTION = (
    "Règles impératives :\n"
    "- N'extrais que ce qui est explicitement écrit dans le texte. N'invente "
    "jamais une donnée absente (URL, coordonnées, date, valeur numérique...).\n"
    "- Si aucun widget ne correspond clairement, ou si tu n'es pas sûr, réponds "
    '"aucun" plutôt que de deviner.\n'
    "- Un seul widget par réponse."
)


def construire_prompt_selection() -> str:
    lignes_catalogue = "\n".join(f'- "{w.cle}" : {w.description}' for w in CATALOGUE)
    return (
        "Tu es un module de sélection de widget d'affichage. Tu reçois la "
        "réponse déjà rédigée d'un assistant conversationnel, avant qu'elle ne "
        "soit montrée à l'utilisateur. Ta tâche : décider si un widget visuel "
        "peut l'enrichir, lequel parmi ceux-ci, et extraire les données "
        "nécessaires à son affichage.\n\n"
        "Widgets disponibles :\n"
        f"{lignes_catalogue}\n\n"
        f"{_REGLES_EXTRACTION}"
    )
