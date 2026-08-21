"""
Orchestrateur bout-en-bout : texte brut de Mistral -> sélection de widget (si
possible) -> filtrage par score de confiance -> rendu HTML. Point d'entrée
unique utilisé par le sandbox.
"""

import html as html_module
import re
import sys
from typing import List, NamedTuple, Optional

from .rendu import palette as pal
from .rendu.afficheur import afficherJoliment
from .selection.confiance import SEUIL_AFFICHAGE, widgets_retenus
from .selection.schemas import ResultatSelection, WidgetCandidat
from .selection.selecteur import selectionner_widget


class ResultatAffichage(NamedTuple):
    """html est toujours prêt à afficher (jamais vide, jamais en échec).
    resultat_selection/erreur donnent de la visibilité sur la décision de
    sélection, pour la console de debug du sandbox — resultat_selection vaut
    None seulement quand l'appel de sélection lui-même a échoué (erreur alors
    renseignée)."""

    html: str
    resultat_selection: Optional[ResultatSelection] = None
    erreur: Optional[str] = None


def _retirer_reference_image(texte: str, url: str) -> str:
    """
    Exception volontaire, propre au widget image : quand une photo est
    retenue, sa référence brute (syntaxe Markdown ![alt](url) ou URL nue) est
    retirée du texte source pour qu'elle n'apparaisse plus qu'une fois, dans
    le widget. Sans ça, la photo s'affichait deux fois — une fois en brut
    (coins droits, rendu Markdown natif) et une fois dans le widget (coins
    arrondis) — et le lien restait visible en texte à côté.

    Les autres widgets ne bénéficient PAS de ce traitement : le texte source
    doit rester compréhensible seul (voir "Philosophie" du README), ce n'est
    qu'en dupliquant réellement le contenu visuel (une photo n'a pas de
    "second sens" au-delà de l'image elle-même) que le retrait est sûr.
    """
    motif_markdown = re.compile(r"!\[[^\]]*\]\(\s*" + re.escape(url) + r"\s*\)")
    texte = motif_markdown.sub("", texte)
    texte = texte.replace(url, "")
    return texte


def _construire_blocs_widgets(candidats: List[WidgetCandidat]) -> List[str]:
    return [
        f"```widget:{widget.type}\n{widget.donnees.model_dump_json(exclude_none=True)}\n```"
        for widget in candidats
    ]


def _ligne_console(candidat: WidgetCandidat) -> str:
    retenu = candidat.confidence >= SEUIL_AFFICHAGE
    couleur = pal.VERT if retenu else pal.TEXTE_FAINT
    statut = "retenu" if retenu else "rejeté"
    pourcent = round(candidat.confidence * 100)
    return f'''
    <div style="padding:8px 0;border-top:1px solid {pal.BORDURE};font-size:12px;">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <span style="font-weight:600;color:{pal.TEXTE};">{html_module.escape(candidat.type)}</span>
        <span style="font-size:11px;font-weight:600;color:{couleur};white-space:nowrap;">{pourcent}% · {statut}</span>
      </div>
      <div style="height:4px;background:{pal.BORDURE};border-radius:2px;margin-top:4px;overflow:hidden;">
        <div style="height:100%;width:{pourcent}%;background:{couleur};"></div>
      </div>
      <div style="color:{pal.TEXTE_MUTED};margin-top:4px;">{html_module.escape(candidat.raison)}</div>
    </div>'''


def _construire_console(resultat: Optional[ResultatSelection], erreur: Optional[str]) -> str:
    """
    Panneau repliable listant TOUS les candidats évalués (retenus ou non) et
    leur score — pas seulement ceux affichés. Construit ici plutôt que dans
    rendu/registre.py : ce n'est pas un widget destiné à l'utilisateur final,
    registre.py n'a pas à connaître la sélection ou le score de confiance.
    """
    if erreur:
        corps = (
            f'<div style="padding:8px 0;font-size:12px;color:#991B1B;">'
            f'⚠️ Sélection en échec : {html_module.escape(erreur)}</div>'
        )
    elif resultat is None or not resultat.candidats:
        corps = (
            f'<div style="padding:8px 0;font-size:12px;color:{pal.TEXTE_FAINT};">'
            f'Aucun candidat évalué.</div>'
        )
    else:
        corps = "".join(_ligne_console(c) for c in resultat.candidats)
    return f'''
    <details style="margin-top:10px;padding-top:10px;border-top:1px solid {pal.BORDURE};">
      <summary style="cursor:pointer;font-size:11px;font-weight:600;color:{pal.TEXTE_FAINT};user-select:none;">Console de sélection</summary>
      {corps}
    </details>'''


def genererAffichage(
    texte_brut: str,
    fichiers: Optional[List] = None,
    api_key: Optional[str] = None,
) -> ResultatAffichage:
    """
    Décide si un ou plusieurs widgets enrichissent texte_brut (selectionner_widget),
    filtre par score de confiance (confiance.widgets_retenus), puis rend le
    résultat en HTML (afficherJoliment). Tout échec de la sélection (clé
    manquante, API indisponible, sortie invalide...) retombe sur texte_brut
    affiché sans widget — jamais de crash, jamais d'écran vide.
    """
    texte_annote = texte_brut
    resultat: Optional[ResultatSelection] = None
    erreur: Optional[str] = None
    try:
        resultat = selectionner_widget(texte_brut, api_key=api_key)
        retenus = widgets_retenus(resultat)

        texte_source = texte_brut
        for widget in retenus:
            if widget.type == "image":
                texte_source = _retirer_reference_image(texte_source, widget.donnees.url)

        blocs = _construire_blocs_widgets(retenus)
        if blocs:
            texte_annote = texte_source.strip() + "\n\n" + "\n\n".join(blocs)
    except Exception as exc:
        erreur = str(exc)
        print(f"[sélection] échec, repli sur texte brut : {exc}", file=sys.stderr)

    html_final = afficherJoliment(
        texte_annote, fichiers, extra_html=_construire_console(resultat, erreur)
    )
    return ResultatAffichage(html=html_final, resultat_selection=resultat, erreur=erreur)
