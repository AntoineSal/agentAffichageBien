"""
Appel Mistral unique : l'agent répond à l'utilisateur ET décide lui-même
d'appeler ou non des outils d'affichage. Remplace, dans le nouveau flux, les
deux appels de l'ancien pipeline (conversation puis sélection).

Aucune boucle d'outils : les tool calls reçus ne sont jamais réexécutés ni
renvoyés au modèle. Ils sont convertis en spécifications de widgets pour le
renderer, et c'est tout.

Sur le streaming — vérifié dans le SDK installé (mistralai 2.9.3), pas supposé :
`client.chat.stream()` existe et `DeltaMessage` porte bien `content` ET
`tool_calls` (une liste de `ToolCall`, chacun avec un champ `index` prévu pour
recoller les fragments d'arguments répartis sur plusieurs chunks). Le streaming
est donc structurellement possible avec cette architecture, et c'est un vrai
argument en sa faveur : le texte peut s'afficher pendant que les arguments des
widgets arrivent encore.

Ce n'est volontairement PAS implémenté ici, pour deux raisons factuelles :
le sandbox PySide6 affiche aujourd'hui un message d'un coup (`setHtml` sur un
QWebEngineView, il n'y a aucun rendu incrémental à alimenter), et le
comportement réel du modèle en streaming (fragmentation des arguments, ordre
d'arrivée, tool calls multiples) n'a pas pu être observé sur un vrai appel. Une
version non streamée propre est donc livrée d'abord, comme demandé — plutôt
qu'un faux streaming qui accumulerait les chunks pour tout afficher à la fin.
"""

import json
import sys
import time
from typing import Any, List, Optional, Tuple

from ..client_mistral import creer_client
from ..metriques import Metriques, extraire_tokens
from .outils import SCHEMA_PAR_CLE, cle_depuis_nom_outil, construire_outils
from .prompt import construire_prompt_generation
from .schemas import ResultatGeneration, ToolCallInvalide, WidgetGenere

# Le tool calling demande un palier de modèle qui le prend en charge. Le projet
# utilise déjà "large" pour la sortie structurée de l'ancien pipeline ; on part
# du même palier, à ajuster empiriquement (coût/fiabilité) une fois le
# mécanisme éprouvé sur de vrais appels.
MODELE_GENERATION = "mistral-large-latest"


def _extraire_texte(contenu: Any) -> str:
    """`AssistantMessage.content` est typé `Union[str, List[ContentChunk], None]`
    dans le SDK : les trois cas sont traités plutôt que de supposer une string."""
    if contenu is None:
        return ""
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        morceaux = []
        for chunk in contenu:
            texte = getattr(chunk, "text", None)
            if isinstance(texte, str):
                morceaux.append(texte)
        return "".join(morceaux)
    return str(contenu)


def _arguments_en_dict(arguments: Any) -> dict:
    """`FunctionCall.arguments` est typé `Union[Dict[str, Any], str]` dans le
    SDK — selon les cas l'API rend le JSON déjà décodé ou une chaîne à parser.
    Lève ValueError si ce n'est ni l'un ni l'autre, ou si le JSON est invalide."""
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        decode = json.loads(arguments)
        if not isinstance(decode, dict):
            raise ValueError("les arguments JSON ne forment pas un objet")
        return decode
    raise ValueError(f"type d'arguments inattendu : {type(arguments).__name__}")


def _texte_arguments(arguments: Any) -> str:
    """Représentation lisible des arguments bruts, pour le diagnostic."""
    if isinstance(arguments, str):
        return arguments
    try:
        return json.dumps(arguments, ensure_ascii=False)
    except Exception:
        return repr(arguments)


def convertir_tool_calls(tool_calls: Optional[List[Any]]) -> Tuple[List[WidgetGenere], List[ToolCallInvalide]]:
    """
    Transforme les tool calls en widgets validés. Chaque appel est traité
    indépendamment : un appel invalide est écarté et consigné, sans empêcher
    les autres d'aboutir ni affecter le Markdown de la réponse.

    Un même outil n'est retenu qu'une fois par réponse. Constaté le 21/08/2026 :
    le modèle a appelé deux fois `afficher_chart` sur la même question, une fois
    avec des données complètes et une fois avec des données tronquées, produisant
    deux graphiques dont un faux. Le prompt le décourage déjà (voir prompt.py),
    mais un prompt n'est pas une garantie — la règle est donc appliquée ici,
    déterministiquement. L'ordre compte : les appels sont validés avant d'être
    dédupliqués, donc un premier appel malformé laisse sa place au suivant plutôt
    que de faire perdre le widget. Les doublons écartés sont consignés dans
    `invalides`, donc visibles dans la console de génération du sandbox.
    """
    widgets: List[WidgetGenere] = []
    invalides: List[ToolCallInvalide] = []
    deja_appeles: set = set()

    for appel in tool_calls or []:
        fonction = getattr(appel, "function", None)
        if fonction is None:
            invalides.append(ToolCallInvalide("(inconnu)", "tool call sans fonction", repr(appel)))
            continue

        nom = getattr(fonction, "name", "") or ""
        bruts = _texte_arguments(getattr(fonction, "arguments", None))

        cle = cle_depuis_nom_outil(nom)
        if cle is None:
            invalides.append(ToolCallInvalide(nom, f"outil inconnu : « {nom} »", bruts))
            continue

        try:
            donnees = SCHEMA_PAR_CLE[cle].model_validate(_arguments_en_dict(fonction.arguments))
        except Exception as exc:
            invalides.append(ToolCallInvalide(nom, f"arguments invalides : {exc}", bruts))
            continue

        if cle in deja_appeles:
            invalides.append(
                ToolCallInvalide(nom, f"doublon : « {nom} » a déjà été appelé dans cette réponse", bruts)
            )
            continue

        deja_appeles.add(cle)
        widgets.append(WidgetGenere(type=cle, donnees=donnees))

    return widgets, invalides


def generer_avec_outils(
    message_utilisateur: str,
    api_key: Optional[str] = None,
    modele: str = MODELE_GENERATION,
) -> ResultatGeneration:
    """
    Un seul appel : la réponse Markdown et les éventuels widgets viennent du
    même modèle, qui voit la question de l'utilisateur et décide en connaissance
    de cause. Lève une exception si l'appel lui-même échoue — c'est à
    l'orchestrateur (pipeline.py) de décider comment le présenter.
    """
    client = creer_client(api_key)

    t0 = time.perf_counter()
    reponse = client.chat.complete(
        model=modele,
        messages=[
            {"role": "system", "content": construire_prompt_generation()},
            {"role": "user", "content": message_utilisateur},
        ],
        tools=construire_outils(),
        # "auto" : le modèle décide s'il appelle un outil. Indispensable ici —
        # "any"/"required" le forceraient à en appeler un à chaque réponse,
        # exactement le contraire de la règle de retenue.
        tool_choice="auto",
        # Autorise plusieurs widgets dans une même réponse (rare, mais possible).
        parallel_tool_calls=True,
    )
    temps_appel_ms = (time.perf_counter() - t0) * 1000

    message = reponse.choices[0].message
    markdown = _extraire_texte(message.content)
    widgets, invalides = convertir_tool_calls(getattr(message, "tool_calls", None))

    for invalide in invalides:
        print(
            f"[génération] widget ignoré ({invalide.nom_outil}) : {invalide.erreur}",
            file=sys.stderr,
        )

    tokens_prompt, tokens_completion, tokens_total = extraire_tokens(reponse)
    metriques = Metriques(
        temps_appel_ms=temps_appel_ms,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        tokens_total=tokens_total,
    )
    return ResultatGeneration(markdown=markdown, widgets=widgets, invalides=invalides, metriques=metriques)
