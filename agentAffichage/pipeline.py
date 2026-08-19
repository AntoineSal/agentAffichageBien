"""
Orchestrateur bout-en-bout : texte brut de Mistral -> sélection de widget (si
possible) -> rendu HTML. Point d'entrée unique utilisé par le sandbox.
"""

import sys
from typing import List, Optional

from .rendu.afficheur import afficherJoliment
from .selection.confiance import widgets_retenus
from .selection.schemas import WidgetCandidat
from .selection.selecteur import selectionner_widget


def _construire_blocs_widgets(candidats: List[WidgetCandidat]) -> List[str]:
    return [
        f"```widget:{widget.type}\n{widget.donnees.model_dump_json(exclude_none=True)}\n```"
        for widget in candidats
    ]


def genererAffichage(
    texte_brut: str,
    fichiers: Optional[List] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Décide si un ou plusieurs widgets enrichissent texte_brut (selectionner_widget),
    puis rend le résultat en HTML (afficherJoliment, inchangé). Tout échec de la
    sélection (clé manquante, API indisponible, sortie invalide...) retombe
    silencieusement sur texte_brut affiché sans widget — jamais de crash, jamais
    d'écran vide.
    """
    texte_annote = texte_brut
    try:
        resultat = selectionner_widget(texte_brut, api_key=api_key)
        blocs = _construire_blocs_widgets(widgets_retenus(resultat))
        if blocs:
            texte_annote = texte_brut + "\n\n" + "\n\n".join(blocs)
    except Exception as exc:
        print(f"[sélection] échec, repli sur texte brut : {exc}", file=sys.stderr)

    return afficherJoliment(texte_annote, fichiers)
