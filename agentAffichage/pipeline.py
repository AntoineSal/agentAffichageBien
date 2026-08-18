"""
Orchestrateur bout-en-bout : texte brut de Mistral -> sélection de widget (si
possible) -> rendu HTML. Point d'entrée unique utilisé par le sandbox.
"""

import sys
from typing import List, Optional

from .rendu.afficheur import afficherJoliment
from .selection.schemas import ResultatSelection
from .selection.selecteur import selectionner_widget


def _construire_bloc_widget(resultat: ResultatSelection) -> str:
    payload = resultat.donnees.model_dump_json(exclude_none=True)
    return f"```widget:{resultat.widget_type}\n{payload}\n```"


def genererAffichage(
    texte_brut: str,
    fichiers: Optional[List] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Décide si un widget enrichit texte_brut (selectionner_widget), puis rend le
    résultat en HTML (afficherJoliment, inchangé). Tout échec de la sélection
    (clé manquante, API indisponible, sortie invalide...) retombe silencieusement
    sur texte_brut affiché sans widget — jamais de crash, jamais d'écran vide.
    """
    texte_annote = texte_brut
    try:
        resultat = selectionner_widget(texte_brut, api_key=api_key)
        if resultat.widget_type != "aucun":
            texte_annote = f"{texte_brut}\n\n{_construire_bloc_widget(resultat)}"
    except Exception as exc:
        print(f"[sélection] échec, repli sur texte brut : {exc}", file=sys.stderr)

    return afficherJoliment(texte_annote, fichiers)
