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
from .selection.catalogue import DEBUT, FIN, POSITION_PAR_CLE
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


# ─── Découpage du Markdown, pour savoir où un bloc widget peut être posé ─────

_FENCE_RE = re.compile(r"^[ \t]*```", re.MULTILINE)
_BLOC_CODE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)\n```", re.DOTALL)


def _zones_code(texte: str) -> List[tuple]:
    """
    Intervalles (début, fin) des blocs de code délimités par ``` ``` ``.

    Nécessaire parce que `rendu/afficheur.py::_WIDGET_BLOCK_RE` n'est PAS
    conscient des fences (vérifié le 24/08/2026) : un bloc widget qui atterrit
    au milieu d'un bloc de code utilisateur est quand même extrait et rendu, ce
    qui casse le bloc de code ET affiche le widget au mauvais endroit. Toute
    insertion doit donc éviter ces zones.
    """
    bornes = [m.start() for m in _FENCE_RE.finditer(texte)]
    zones = []
    for i in range(0, len(bornes) - 1, 2):
        fin_ligne = texte.find("\n", bornes[i + 1])
        zones.append((bornes[i], len(texte) if fin_ligne == -1 else fin_ligne))
    return zones


def _dans_zone_code(position: int, zones: Sequence[tuple]) -> bool:
    return any(debut <= position < fin for debut, fin in zones)


def _bornes_bloc(texte: str, position: int) -> tuple:
    """Début et fin du bloc Markdown (paragraphe, séparé par une ligne vide)
    qui contient `position`."""
    debut = texte.rfind("\n\n", 0, position)
    debut = 0 if debut == -1 else debut + 2
    fin = texte.find("\n\n", position)
    return debut, len(texte) if fin == -1 else fin


def _poser_a_la_place(texte: str, debut: int, fin: int, bloc: str) -> str:
    """
    Substitue le bloc widget à `texte[debut:fin]`, sans jamais l'insérer au
    milieu d'un paragraphe : un bloc widget doit être séparé par des lignes
    vides, sinon le parser Markdown l'absorbe dans le paragraphe voisin (et
    l'extension `nl2br`, active, rend le texte sensible aux retours simples).

    Deux cas :
    - la référence était seule dans son paragraphe (cas courant : une image ou
      un bloc de code sur sa propre ligne) → le widget prend toute la place ;
    - la référence était au fil d'une phrase → la phrase est conservée, amputée
      de la référence, et le widget est posé juste après elle.
    """
    bloc_debut, bloc_fin = _bornes_bloc(texte, debut)
    reste = (texte[bloc_debut:debut] + texte[fin:bloc_fin]).strip()
    remplacement = f"{reste}\n\n{bloc}" if reste else bloc
    return texte[:bloc_debut] + remplacement + texte[bloc_fin:]


def _remplacer_reference_image(texte: str, url: str, bloc: str) -> tuple:
    """
    Le widget image prend la place de la référence que le texte fait déjà à
    cette image (syntaxe Markdown ![alt](url) ou URL nue).

    Historiquement cette référence était seulement RETIRÉE, et le widget ajouté
    en fin de réponse : la photo s'affichait sinon deux fois — une fois en brut
    (coins droits, rendu Markdown natif) et une fois dans le widget. La
    substitution donne le même résultat sur ce point, mais garde la photo là où
    la réponse en parle, ce qui est le comportement demandé le 24/08/2026.

    Renvoie (placé, texte). `placé` est faux quand le texte ne référence pas
    l'image — le modèle a alors appelé l'outil sans que sa réponse mentionne
    l'URL, et c'est la position par défaut du catalogue qui s'applique.
    """
    motifs = [
        re.compile(r"!\[[^\]]*\]\(\s*" + re.escape(url) + r"\s*\)"),
        re.compile(re.escape(url)),
    ]
    zones = _zones_code(texte)

    for motif in motifs:
        for occurrence in motif.finditer(texte):
            if _dans_zone_code(occurrence.start(), zones):
                continue
            texte = _poser_a_la_place(texte, occurrence.start(), occurrence.end(), bloc)
            # Le modèle cite parfois la même URL deux fois (image Markdown puis
            # lien nu). Les occurrences restantes sont retirées, sans quoi elles
            # s'afficheraient à côté du widget.
            avant, apres = texte.split(bloc, 1)
            for reste in motifs:
                apres = reste.sub("", apres)
            return True, avant + bloc + apres

    return False, texte


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


def _remplacer_bloc_code(texte: str, code: str, bloc: str) -> tuple:
    """
    Même principe que `_remplacer_reference_image`, pour le widget `code` :
    quand le modèle écrit le code dans sa réponse ET appelle l'outil, le code
    apparaissait deux fois — une fois en bloc Markdown brut, une fois dans le
    widget (constaté le 20/08/2026 sur une demande de fonction Fibonacci). Le
    widget prend maintenant la place du bloc Markdown au lieu d'être relégué en
    fin de réponse : la phrase qui introduit le code reste juste au-dessus.

    Deux passes pour identifier le bloc, afin de ne jamais toucher à un autre
    extrait de code de la réponse :

    1. Les blocs identiques au widget (espaces ignorés) — cas courant.
    2. À défaut, le bloc le PLUS proche, et seulement lui, s'il dépasse
       `_SEUIL_SIMILARITE_CODE`. Cette seconde passe corrige un cas réel
       constaté le 21/08/2026 : le modèle reformule légèrement le code entre
       son texte et son appel d'outil (commentaire ajouté, espaces autour des
       opérateurs), et la comparaison exacte laissait alors passer le doublon.

    Renvoie (placé, texte), comme `_remplacer_reference_image`.
    """
    cible = _normaliser_code(code)
    if not cible:
        return False, texte

    blocs = list(_BLOC_CODE_RE.finditer(texte))
    if not blocs:
        return False, texte

    correspondants = [b for b in blocs if _normaliser_code(b.group(1)) == cible]
    if not correspondants:
        if len(cible) < _TAILLE_MINI_CODE_FLOU:
            return False, texte
        meilleur = max(
            blocs,
            key=lambda b: SequenceMatcher(None, cible, _normaliser_code(b.group(1))).ratio(),
        )
        ratio = SequenceMatcher(None, cible, _normaliser_code(meilleur.group(1))).ratio()
        if ratio < _SEUIL_SIMILARITE_CODE:
            return False, texte
        correspondants = [meilleur]

    # Le premier bloc cède sa place au widget ; les éventuels doublons exacts
    # qui suivent sont simplement retirés. On repart de la fin pour que les
    # positions déjà calculées restent valides.
    premier, suivants = correspondants[0], correspondants[1:]
    for autre in reversed(suivants):
        texte = texte[: autre.start()] + texte[autre.end():]
    return True, _poser_a_la_place(texte, premier.start(), premier.end(), bloc)


def _bloc_widget(widget: PorteurWidget) -> str:
    """Sérialise un widget vers le contrat déjà consommé par le renderer.
    Accepte indifféremment les `WidgetCandidat` de l'ancien flux et les
    `WidgetGenere` du nouveau : les deux exposent `.type` et `.donnees`, et
    c'est tout ce dont cette fonction a besoin (cf. `PorteurWidget`)."""
    return f"```widget:{widget.type}\n{widget.donnees.model_dump_json(exclude_none=True)}\n```"


def _construire_blocs_widgets(widgets: Sequence[PorteurWidget]) -> List[str]:
    return [_bloc_widget(widget) for widget in widgets]


def _annoter_texte(texte_brut: str, widgets: Sequence[PorteurWidget]) -> str:
    """
    Assemble le texte final envoyé au renderer : le Markdown d'origine, avec les
    blocs widget posés à leur place.

    Le renderer place chaque widget là où son bloc apparaît (`_extraire_widgets`
    le remplace par un marqueur, `_injecter_widgets` réinjecte le HTML au
    marqueur) — la position est donc entièrement décidée ici, et `rendu/` n'a
    pas à la connaître.

    Trois cas, dans cet ordre :

    1. **Le texte dit déjà où va le widget** — `image` et `code` sont référencés
       explicitement dans la réponse. Le widget prend la place de cette
       référence : la photo reste là où la phrase en parle, le code sous la
       phrase qui l'introduit. Aucune information n'est demandée au modèle.
    2. **Sinon, la position par défaut du type** (`selection/catalogue.py`) :
       un widget qui RÉPOND à la question passe avant le texte (`card`, `stats`,
       `image` non référencée), un widget qui APPUIE une démonstration déjà
       écrite passe après (`chart`, `table`, `timeline`, `file`, `code` non
       référencé).
    3. À l'intérieur d'un même emplacement, l'ordre d'appel du modèle est
       conservé — il est déjà déterministe, et rien n'a démontré le besoin d'un
       classement supplémentaire.

    Un champ de position choisi par le modèle (phase 2) ou un ancrage fin
    (phase 3) viendraient se greffer entre 1 et 2, sans rien changer d'autre —
    voir FEUILLE_DE_ROUTE_WIDGETS_INTEGRES.md.
    """
    if not widgets:
        return texte_brut

    texte = texte_brut
    en_tete: List[str] = []
    en_pied: List[str] = []

    for widget in widgets:
        bloc = _bloc_widget(widget)

        place = False
        if widget.type == "image":
            place, texte = _remplacer_reference_image(texte, widget.donnees.url, bloc)
        elif widget.type == "code":
            place, texte = _remplacer_bloc_code(texte, widget.donnees.code, bloc)
        if place:
            continue

        if POSITION_PAR_CLE.get(widget.type, FIN) == DEBUT:
            en_tete.append(bloc)
        else:
            en_pied.append(bloc)

    morceaux = en_tete + [texte.strip()] + en_pied
    return "\n\n".join(morceau for morceau in morceaux if morceau)


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
