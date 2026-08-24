"""
Orchestrateur bout-en-bout. Deux flux coexistent volontairement, pour pouvoir
les comparer sur les mêmes requêtes :

- `genererAffichage()` — ANCIEN flux : texte déjà rédigé -> appel de sélection
  dédié -> filtrage par score de confiance -> rendu.
- `genererAffichageAvecOutils()` — NOUVEAU flux : un seul appel Mistral qui
  répond ET appelle lui-même des outils d'affichage -> rendu. Ne passe jamais
  par `selection/`.

Les deux partagent la même étape de rendu (`afficherJoliment`) et la même
sérialisation des blocs widget (`_construire_blocs_widgets`).
"""

import html as html_module
import re
import sys
import time
from difflib import SequenceMatcher
from typing import List, NamedTuple, Optional, Sequence

from .generation.generateur import generer_avec_outils
from .generation.schemas import PorteurWidget, ResultatGeneration
from .metriques import Metriques
from .rendu import palette as pal
from .rendu.afficheur import afficherJoliment
from .selection.confiance import SEUIL_AFFICHAGE, widgets_retenus
from .selection.schemas import ResultatSelection, WidgetCandidat
from .selection.selecteur import selectionner_widget


class ResultatAffichage(NamedTuple):
    """html est toujours prêt à afficher (jamais vide, jamais en échec).
    Les autres champs donnent de la visibilité sur la décision, pour la console
    de debug du sandbox : `resultat_selection` est renseigné par l'ancien flux,
    `resultat_generation` par le nouveau, jamais les deux. `erreur` est
    renseignée quand l'appel Mistral lui-même a échoué."""

    html: str
    resultat_selection: Optional[ResultatSelection] = None
    erreur: Optional[str] = None
    resultat_generation: Optional[ResultatGeneration] = None


def _retirer_reference_image(texte: str, url: str) -> str:
    """
    Exception volontaire, propre au widget image : quand une photo est
    retenue, sa référence brute (syntaxe Markdown ![alt](url) ou URL nue) est
    retirée du texte source pour qu'elle n'apparaisse plus qu'une fois, dans
    le widget. Sans ça, la photo s'affichait deux fois — une fois en brut
    (coins droits, rendu Markdown natif) et une fois dans le widget (coins
    arrondis) — et le lien restait visible en texte à côté.

    Seuls `image` et `code` bénéficient de ce traitement (voir aussi
    `_retirer_bloc_code`) : le texte source doit rester compréhensible seul
    (voir "Philosophie" du README), et ce n'est que lorsque le widget reprend
    exactement le même contenu — une image, un bloc de code — que le retrait ne
    perd aucune information.
    """
    motif_markdown = re.compile(r"!\[[^\]]*\]\(\s*" + re.escape(url) + r"\s*\)")
    texte = motif_markdown.sub("", texte)
    texte = texte.replace(url, "")
    return texte


# Un bloc Markdown est considéré comme repris par le widget au-delà de ce taux
# de similarité. Mesuré sur les cas réels : une reformulation légère du même
# code (commentaire ajouté, espaces autour des opérateurs) donne ~0.93, alors
# que deux fonctions différentes de forme voisine plafonnent vers 0.65-0.69. Le
# seuil est placé dans cet écart, du côté prudent.
_SEUIL_SIMILARITE_CODE = 0.85

# En dessous de cette taille, un écart d'un caractère fait bouger la similarité
# de plusieurs points : la comparaison floue n'y est pas fiable, seul le match
# exact s'applique.
_TAILLE_MINI_CODE_FLOU = 40


def _normaliser_code(source: str) -> str:
    return "".join(source.split())


def _retirer_bloc_code(texte: str, code: str) -> str:
    """
    Même principe que `_retirer_reference_image`, pour le widget `code` : quand
    le modèle écrit le code dans sa réponse ET appelle l'outil, le code
    apparaissait deux fois — une fois en bloc Markdown brut, une fois dans le
    widget (constaté le 20/08/2026 sur une demande de fonction Fibonacci).

    Deux passes, pour ne jamais supprimer un autre extrait de code de la
    réponse :

    1. Tout bloc dont le contenu est identique au widget (espaces ignorés) est
       retiré — c'est le cas courant.
    2. Si aucun bloc n'est identique, le bloc le PLUS proche est retiré, et
       seulement lui, à condition de dépasser `_SEUIL_SIMILARITE_CODE`. Cette
       seconde passe corrige un cas réel constaté le 21/08/2026 : le modèle
       reformule légèrement le code entre son texte et son appel d'outil
       (commentaire ajouté, espaces autour des opérateurs), et la comparaison
       exacte laissait alors passer le doublon.
    """
    cible = _normaliser_code(code)
    if not cible:
        return texte

    blocs = list(re.finditer(r"```[a-zA-Z0-9_+-]*\n(.*?)\n```", texte, flags=re.DOTALL))
    if not blocs:
        return texte

    exacts = [b for b in blocs if _normaliser_code(b.group(1)) == cible]
    if exacts:
        a_retirer = exacts
    elif len(cible) < _TAILLE_MINI_CODE_FLOU:
        return texte
    else:
        meilleur = max(
            blocs,
            key=lambda b: SequenceMatcher(None, cible, _normaliser_code(b.group(1))).ratio(),
        )
        ratio = SequenceMatcher(None, cible, _normaliser_code(meilleur.group(1))).ratio()
        if ratio < _SEUIL_SIMILARITE_CODE:
            return texte
        a_retirer = [meilleur]

    resultat = texte
    for bloc in reversed(a_retirer):
        resultat = resultat[: bloc.start()] + resultat[bloc.end():]
    return resultat


def _construire_blocs_widgets(widgets: Sequence[PorteurWidget]) -> List[str]:
    """Sérialise des widgets vers le contrat déjà consommé par le renderer.
    Accepte indifféremment les `WidgetCandidat` de l'ancien flux et les
    `WidgetGenere` du nouveau : les deux exposent `.type` et `.donnees`, et
    c'est tout ce dont cette fonction a besoin (cf. `PorteurWidget`)."""
    return [
        f"```widget:{widget.type}\n{widget.donnees.model_dump_json(exclude_none=True)}\n```"
        for widget in widgets
    ]


def _annoter_texte(texte_brut: str, widgets: Sequence[PorteurWidget]) -> str:
    """
    Assemble le texte final envoyé au renderer : le texte d'origine, débarrassé
    des références d'image reprises en widget, suivi des blocs widget.

    Les blocs sont ajoutés à la fin, pas intercalés dans le texte : le renderer
    place chaque widget là où son bloc apparaît, donc il n'a besoin d'aucune
    information de position pour fonctionner. Si un placement plus fin devenait
    souhaitable (texte / graphique / texte), la voie propre serait un champ
    d'ancrage optionnel — un court extrait verbatim du Markdown après lequel
    insérer le widget, avec repli en fin de texte si l'extrait est introuvable.
    Non implémenté volontairement : ce serait un champ que le renderer n'utilise
    pas, pour un besoin que rien n'a encore démontré.
    """
    texte = texte_brut
    for widget in widgets:
        if widget.type == "image":
            texte = _retirer_reference_image(texte, widget.donnees.url)
        elif widget.type == "code":
            texte = _retirer_bloc_code(texte, widget.donnees.code)

    blocs = _construire_blocs_widgets(widgets)
    if not blocs:
        return texte_brut
    return texte.strip() + "\n\n" + "\n\n".join(blocs)


def _ligne_metriques(m: Metriques) -> str:
    """Bandeau en tête de chaque console : temps d'appel Mistral vs temps de
    traitement local, et tokens consommés quand l'API les fournit (voir
    metriques.py — préservé aussi bien par l'ancien flux, sortie structurée,
    que par le nouveau, tool calling)."""
    if m.tokens_total is not None:
        tokens_txt = f"{m.tokens_prompt or 0}+{m.tokens_completion or 0}={m.tokens_total} tokens"
    else:
        tokens_txt = "tokens indisponibles"
    return (
        f'<div style="padding:0 0 10px;font-size:11px;color:{pal.TEXTE_MUTED};'
        f"font-family:'SF Mono',Menlo,monospace;\">"
        f"⏱ {m.temps_total_ms:.0f} ms total — appel {m.temps_appel_ms:.0f} ms, "
        f"traitement {m.temps_traitement_ms:.0f} ms · 🔤 {tokens_txt}"
        f"</div>"
    )


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


def _construire_console(
    resultat: Optional[ResultatSelection], erreur: Optional[str], metriques: Metriques
) -> str:
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
    return _panneau_console("Console de sélection", _ligne_metriques(metriques) + corps)


def _panneau_console(titre: str, corps: str) -> str:
    return f'''
    <details style="margin-top:10px;padding-top:10px;border-top:1px solid {pal.BORDURE};">
      <summary style="cursor:pointer;font-size:11px;font-weight:600;color:{pal.TEXTE_FAINT};user-select:none;">{html_module.escape(titre)}</summary>
      {corps}
    </details>'''


def _console_generation(
    resultat: Optional[ResultatGeneration], erreur: Optional[str], metriques: Metriques
) -> str:
    """
    Équivalent de `_construire_console` pour le nouveau flux. Pas de score ni de
    barre de confiance : dans cette architecture, le modèle générateur décide
    lui-même d'appeler un outil, il n'y a plus de second juge à qui demander une
    note. Ce qui est utile à voir ici, c'est ce qui a été appelé — et surtout ce
    qui a été refusé, avec la raison.
    """
    if erreur:
        corps = (
            f'<div style="padding:8px 0;font-size:12px;color:#991B1B;">'
            f'⚠️ Génération en échec : {html_module.escape(erreur)}</div>'
        )
    elif resultat is None or (not resultat.widgets and not resultat.invalides):
        corps = (
            f'<div style="padding:8px 0;font-size:12px;color:{pal.TEXTE_FAINT};">'
            f'Aucun outil d\'affichage appelé.</div>'
        )
    else:
        # Les données envoyées par le modèle sont affichées telles quelles :
        # sans elles, un widget qui s'affiche mal (URL d'image erronée, valeur
        # inattendue) est indiagnosticable depuis l'interface.
        lignes = [
            f'<div style="padding:8px 0;border-top:1px solid {pal.BORDURE};font-size:12px;">'
            f'<span style="font-weight:600;color:{pal.TEXTE};">{html_module.escape(w.type)}</span>'
            f'<span style="font-size:11px;font-weight:600;color:{pal.VERT};margin-left:8px;">appelé</span>'
            f'<pre style="margin:4px 0 0;padding:6px 8px;background:{pal.FOND_DOUX};border-radius:6px;'
            f'font-size:10.5px;white-space:pre-wrap;word-break:break-all;color:{pal.TEXTE_MUTED};">'
            f'{html_module.escape(w.donnees.model_dump_json(exclude_none=True))}</pre>'
            f'</div>'
            for w in resultat.widgets
        ]
        lignes += [
            f'<div style="padding:8px 0;border-top:1px solid {pal.BORDURE};font-size:12px;">'
            f'<span style="font-weight:600;color:{pal.TEXTE};">{html_module.escape(i.nom_outil)}</span>'
            f'<span style="font-size:11px;font-weight:600;color:#991B1B;margin-left:8px;">ignoré</span>'
            f'<div style="color:{pal.TEXTE_MUTED};margin-top:4px;">{html_module.escape(i.erreur)}</div>'
            f'<pre style="margin:4px 0 0;padding:6px 8px;background:{pal.FOND_DOUX};border-radius:6px;'
            f'font-size:10.5px;white-space:pre-wrap;word-break:break-all;color:{pal.TEXTE_MUTED};">'
            f'{html_module.escape(i.arguments_bruts[:400])}</pre>'
            f'</div>'
            for i in resultat.invalides
        ]
        corps = "".join(lignes)
    return _panneau_console("Console de génération", _ligne_metriques(metriques) + corps)


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
    metriques = Metriques()
    try:
        t0 = time.perf_counter()
        appel = selectionner_widget(texte_brut, api_key=api_key)
        resultat = appel.resultat
        texte_annote = _annoter_texte(texte_brut, widgets_retenus(resultat))
        temps_traitement_ms = (time.perf_counter() - t0) * 1000 - appel.metriques.temps_appel_ms
        metriques = appel.metriques._replace(temps_traitement_ms=max(temps_traitement_ms, 0.0))
    except Exception as exc:
        erreur = str(exc)
        print(f"[sélection] échec, repli sur texte brut : {exc}", file=sys.stderr)

    html_final = afficherJoliment(
        texte_annote, fichiers, extra_html=_construire_console(resultat, erreur, metriques)
    )
    return ResultatAffichage(html=html_final, resultat_selection=resultat, erreur=erreur)


def genererAffichageAvecOutils(
    message_utilisateur: str,
    fichiers: Optional[List] = None,
    api_key: Optional[str] = None,
) -> ResultatAffichage:
    """
    NOUVEAU flux : un seul appel Mistral produit la réponse Markdown ET les
    éventuels appels d'outils d'affichage. `selection/` n'intervient jamais ici.

    Le Markdown ne dépend jamais du sort des widgets : un tool call invalide est
    écarté en amont par `convertir_tool_calls`, et même si l'annotation échouait,
    le texte est rendu tel quel. Si l'appel Mistral lui-même échoue, il n'y a par
    construction aucune réponse à afficher (contrairement à l'ancien flux où le
    texte venait d'un appel séparé) — on affiche alors un message d'erreur lisible
    plutôt qu'une carte vide.
    """
    resultat: Optional[ResultatGeneration] = None
    erreur: Optional[str] = None
    metriques = Metriques()
    try:
        t0 = time.perf_counter()
        resultat = generer_avec_outils(message_utilisateur, api_key=api_key)
        texte_annote = _annoter_texte(resultat.markdown, resultat.widgets)
        base = resultat.metriques or Metriques()
        temps_traitement_ms = (time.perf_counter() - t0) * 1000 - base.temps_appel_ms
        metriques = base._replace(temps_traitement_ms=max(temps_traitement_ms, 0.0))
    except Exception as exc:
        erreur = str(exc)
        print(f"[génération] échec de l'appel : {exc}", file=sys.stderr)
        texte_annote = f"⚠️ La génération a échoué : {exc}"

    html_final = afficherJoliment(
        texte_annote, fichiers, extra_html=_console_generation(resultat, erreur, metriques)
    )
    return ResultatAffichage(
        html=html_final, erreur=erreur, resultat_generation=resultat
    )
