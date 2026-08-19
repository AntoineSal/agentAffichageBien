"""
Filtrage des candidats par score de confiance.

Décision volontairement déterministe et séparée du modèle : le LLM calcule un
confidence par candidat (voir prompt.py), mais c'est ce module — du code
Python ordinaire, testable et modifiable sans toucher au prompt — qui décide
quels candidats sont réellement affichés. Garder ce seuil ici plutôt que de
compter sur le modèle pour l'appliquer lui-même le rend inspectable et facile
à ajuster (cf. le futur outil de debug évoqué par l'utilisateur : il doit
pouvoir régler ce seuil et rejouer des phrases sans re-toucher au prompt).
"""

from typing import List

from .schemas import ResultatSelection, WidgetCandidat

# Bande "0.75–0.89 : bonne pertinence → affichage possible" de la spec fournie
# par l'utilisateur. Volontairement élevé : on privilégie les faux négatifs
# (widget manqué) aux faux positifs (widget inutile affiché).
SEUIL_AFFICHAGE = 0.75


def widgets_retenus(resultat: ResultatSelection) -> List[WidgetCandidat]:
    """Sous-ensemble de resultat.candidats qui franchit SEUIL_AFFICHAGE — c'est
    cette liste, et seulement elle, que pipeline.py doit rendre en widgets."""
    return [c for c in resultat.candidats if c.confidence >= SEUIL_AFFICHAGE]
