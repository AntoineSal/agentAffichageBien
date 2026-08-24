"""
Déclaration des 8 widgets comme outils d'affichage pour Mistral.

Rien n'est redéfini ici : les schémas d'arguments sont générés directement
depuis les modèles `Donnees*` de `selection/schemas.py`, et les descriptions
depuis `selection/catalogue.py`. Ajouter un widget au catalogue suffit donc à
le rendre appelable par le modèle, exactement comme cela met déjà à jour le
prompt de l'ancien pipeline.

Ce ne sont PAS des outils fonctionnels : un appel ne déclenche aucune exécution
et ne renvoie aucun résultat au modèle. Le tool call EST le résultat — une
spécification de widget destinée au renderer. Il n'y a donc jamais de second
tour d'appel (pas de boucle LLM → tool → résultat → LLM).
"""

from typing import Any, Dict, List, Optional, Type

from mistralai.extra.utils._pydantic_helper import rec_strict_json_schema
from pydantic import BaseModel

from ..selection.catalogue import CATALOGUE, DescripteurWidget

# Les noms d'outils doivent être des identifiants ; la clé du catalogue
# ("chart", "card"...) est préfixée pour dire au modèle ce que l'appel fait.
PREFIXE_OUTIL = "afficher_"

# `strict` demande à l'API de contraindre la génération des arguments au schéma.
# Notre propre validation Pydantic à la réception (voir generateur.py) reste la
# garantie réelle : elle ne dépend pas du comportement exact de l'API, et un
# widget invalide est de toute façon écarté sans toucher au Markdown.
SCHEMA_STRICT = True


# Clé de widget -> modèle Pydantic de ses données, pour valider les arguments
# d'un tool call à la réception (voir generateur.py).
SCHEMA_PAR_CLE: Dict[str, Type[BaseModel]] = {w.cle: w.schema for w in CATALOGUE}


def nom_outil(cle_widget: str) -> str:
    return f"{PREFIXE_OUTIL}{cle_widget}"


def cle_depuis_nom_outil(nom: str) -> Optional[str]:
    """Inverse de nom_outil(). Renvoie None si le nom ne correspond à aucun
    widget connu — un outil inventé par le modèle ne peut donc pas passer."""
    if not nom.startswith(PREFIXE_OUTIL):
        return None
    cle = nom[len(PREFIXE_OUTIL):]
    return cle if cle in SCHEMA_PAR_CLE else None


def _description(widget: DescripteurWidget) -> str:
    """Les règles propres à un widget vivent dans la description de son outil
    plutôt que dans le prompt système : le modèle les voit attachées à l'outil
    au moment de décider de l'appeler, et on évite de dupliquer le catalogue."""
    return (
        f"{widget.objectif}\n"
        f"UTILISER QUAND : {widget.utiliser_quand}\n"
        f"NE PAS UTILISER QUAND : {widget.ne_pas_utiliser_quand}"
    )


def construire_outils() -> List[Dict[str, Any]]:
    """Les 8 widgets du catalogue, au format `tools` de l'API Mistral."""
    outils: List[Dict[str, Any]] = []
    for widget in CATALOGUE:
        # model_json_schema() rend un dict neuf à chaque appel, et
        # rec_strict_json_schema le modifie en place : pas d'effet de bord entre
        # deux constructions. additionalProperties:false y est posé
        # récursivement — le modèle ne peut pas ajouter de champ hors schéma.
        parametres = rec_strict_json_schema(widget.schema.model_json_schema())
        fonction: Dict[str, Any] = {
            "name": nom_outil(widget.cle),
            "description": _description(widget),
            "parameters": parametres,
        }
        if SCHEMA_STRICT:
            fonction["strict"] = True
        outils.append({"type": "function", "function": fonction})
    return outils
