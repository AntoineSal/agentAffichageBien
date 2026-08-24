"""
Appel Mistral dédié à la sélection de widget, séparé de la conversation avec
l'utilisateur. Reçoit le texte brut d'une réponse déjà rédigée et renvoie un
ResultatSelection validé, ou lève une exception si l'appel échoue — c'est à
l'orchestrateur (pipeline.py, phase 3) de décider comment retomber sur le texte
brut en cas d'échec, pas à cette fonction.
"""

import locale
import os
import time
from typing import NamedTuple, Optional

from mistralai.client.sdk import Mistral

from ..metriques import Metriques, extraire_tokens
from .prompt import construire_prompt_selection
from .schemas import ResultatSelection


class AppelSelection(NamedTuple):
    """resultat est le ResultatSelection validé ; metriques porte le temps
    d'appel et les tokens consommés — jamais mêlés à ResultatSelection
    lui-même, qui EST le schéma envoyé à Mistral en sortie structurée : lui
    ajouter des champs annexes changerait ce qu'on demande au modèle de
    produire."""

    resultat: ResultatSelection
    metriques: Metriques

# Choisi pour cette première validation du mécanisme : seul le palier "Large"
# était confirmé prendre en charge les Custom Structured Outputs au moment de
# nos recherches. À ajuster empiriquement (coût/fiabilité) une fois le
# mécanisme prouvé bout en bout.
MODELE_SELECTION = "mistral-large-latest"


def selectionner_widget(texte_brut: str, api_key: Optional[str] = None) -> AppelSelection:
    """
    Décide si un widget du catalogue peut enrichir texte_brut, et avec quelles
    données. N'écrit jamais dans texte_brut : c'est un appel de lecture pure.
    """
    cle = api_key or os.getenv("MISTRAL_API_KEY")
    if not cle:
        raise RuntimeError(
            "Clé API Mistral manquante : passez api_key, ou définissez la "
            "variable d'environnement MISTRAL_API_KEY."
        )

    # Le prompt système contient des caractères accentués. Si l'encodage par
    # défaut de l'interpréteur n'est pas UTF-8 (LANG/LC_ALL absents du shell),
    # une bibliothèque de la chaîne d'appel (mistralai/httpx) échoue avec une
    # UnicodeEncodeError cryptique. Constaté et reproduit le 17/08/2026 : le
    # correctif est PYTHONUTF8=1, à définir avant le lancement de l'interpréteur
    # (impossible à corriger depuis l'intérieur du script une fois démarré).
    encodage = locale.getpreferredencoding()
    if encodage.lower() not in ("utf-8", "utf8"):
        raise RuntimeError(
            f"Encodage de l'environnement non-UTF-8 détecté ({encodage!r}) : "
            "relancez avec PYTHONUTF8=1 avant l'appel Mistral, par exemple "
            '"PYTHONUTF8=1 .venv/bin/python3 verifier_selection.py".'
        )

    client = Mistral(api_key=cle)

    t0 = time.perf_counter()
    reponse = client.chat.parse(
        model=MODELE_SELECTION,
        messages=[
            {"role": "system", "content": construire_prompt_selection()},
            {"role": "user", "content": texte_brut},
        ],
        response_format=ResultatSelection,
    )
    temps_appel_ms = (time.perf_counter() - t0) * 1000

    resultat = reponse.choices[0].message.parsed
    if resultat is None:
        raise RuntimeError(
            "Mistral n'a pas renvoyé une sortie exploitable pour la sélection de widget."
        )

    tokens_prompt, tokens_completion, tokens_total = extraire_tokens(reponse)
    metriques = Metriques(
        temps_appel_ms=temps_appel_ms,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        tokens_total=tokens_total,
    )
    return AppelSelection(resultat, metriques)
