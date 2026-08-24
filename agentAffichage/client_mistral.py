"""
Création du client Mistral, partagée par les appels de l'agent.

Note volontaire : `selection/selecteur.py` embarque aujourd'hui sa propre copie
de cette logique. Elle n'a PAS été refactorée pour utiliser ce module — l'ancien
pipeline de sélection doit rester intact tant que la nouvelle approche (tools
d'affichage) n'est pas validée en conditions réelles. Les deux copies seront
unifiées ici le jour où l'ancien chemin sera retiré.
"""

import locale
import os
from typing import Optional

from mistralai.client.sdk import Mistral


def creer_client(api_key: Optional[str] = None) -> Mistral:
    """Résout la clé API et vérifie l'environnement avant tout appel réseau."""
    cle = api_key or os.getenv("MISTRAL_API_KEY")
    if not cle:
        raise RuntimeError(
            "Clé API Mistral manquante : passez api_key, ou définissez la "
            "variable d'environnement MISTRAL_API_KEY."
        )

    # Les prompts contiennent des caractères accentués. Si l'encodage par défaut
    # de l'interpréteur n'est pas UTF-8 (LANG/LC_ALL absents du shell), une
    # bibliothèque de la chaîne d'appel (mistralai/httpx) échoue avec une
    # UnicodeEncodeError cryptique. Constaté et reproduit le 17/08/2026 : le
    # correctif est PYTHONUTF8=1, à définir avant le lancement de l'interpréteur
    # (impossible à corriger depuis l'intérieur du script une fois démarré).
    encodage = locale.getpreferredencoding()
    if encodage.lower() not in ("utf-8", "utf8"):
        raise RuntimeError(
            f"Encodage de l'environnement non-UTF-8 détecté ({encodage!r}) : "
            "relancez avec PYTHONUTF8=1 avant l'appel Mistral, par exemple "
            '"PYTHONUTF8=1 .venv/bin/python3 main.py".'
        )

    return Mistral(api_key=cle)
