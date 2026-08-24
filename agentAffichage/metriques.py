"""
Mesures de performance partagées par les deux flux — pour pouvoir les comparer
honnêtement sur le même terrain (temps d'appel Mistral, temps de traitement
local, tokens consommés).
"""

from typing import NamedTuple, Optional, Tuple


class Metriques(NamedTuple):
    """Toutes les durées en millisecondes.

    `temps_appel_ms` couvre uniquement l'appel réseau à Mistral, mesuré au plus
    près (juste avant/après l'appel SDK) — la part qu'aucune optimisation
    locale ne réduira jamais.

    `temps_traitement_ms` couvre tout notre code entre la réponse de Mistral et
    le texte annoté prêt à être rendu (conversion des tool calls ou filtrage
    par confiance, construction des blocs widget) — mais pas le templating
    HTML final : le mesurer nécessiterait de modifier la page après coup pour y
    insérer sa propre durée, un paradoxe évité plutôt que bricolé. Ce
    templating est de toute façon du formatage de chaînes pur, sans I/O,
    négligeable en pratique.

    `tokens_*` valent None quand ils ne sont pas connus : appel qui a échoué
    avant d'obtenir une réponse, ou test qui simule une réponse sans les
    fournir.
    """

    temps_appel_ms: float = 0.0
    temps_traitement_ms: float = 0.0
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    tokens_total: Optional[int] = None

    @property
    def temps_total_ms(self) -> float:
        return self.temps_appel_ms + self.temps_traitement_ms


def extraire_tokens(reponse) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Lit usage.{prompt,completion,total}_tokens sur une réponse Mistral, sans
    jamais lever : une réponse simulée dans les tests peut ne pas porter cet
    attribut, et ça ne doit jamais faire échouer l'appel réel pour autant.

    Vérifié dans le SDK installé (mistralai 2.9.3) : ChatCompletionResponse
    porte bien `usage: UsageInfo` avec prompt_tokens/completion_tokens/
    total_tokens, et ce champ est préservé par client.chat.parse() (l'ancien
    flux) — ParsedChatCompletionResponse hérite de ChatCompletionResponse et
    reconstruit ses champs depuis la réponse d'origine sans en perdre aucun.
    """
    usage = getattr(reponse, "usage", None)
    if usage is None:
        return None, None, None
    return (
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
        getattr(usage, "total_tokens", None),
    )
