"""
Module principal pour l'agent d'affichage (à implémenter par le stagiaire).

La fonction afficherJoliment reçoit un texte et des fichiers,
et doit retourner un code HTML/CSS/JS autonome.
"""

from typing import Dict, List, Optional, Tuple
import html
import json
import re

import markdown as md

from . import palette as pal
from . import registre

_MD_EXTENSIONS = ["extra", "sane_lists", "nl2br"]

# Bloc réservé qu'un agent (ou un test manuel) peut utiliser dans sa réponse
# pour déclencher un composant du registre plutôt que du texte formaté :
#   ```widget:weather
#   {"location": "Paris", ...}
#   ```
_WIDGET_BLOCK_RE = re.compile(r"```widget:(\w+)\s*\n(.*?)\n```", re.DOTALL)

# Dispatch type de widget -> fonction du registre. Chaque fonction reçoit le
# JSON décodé du bloc et renvoie un fragment HTML autonome.
_REGISTRE_WIDGETS = {
    # Widgets génériques (catalogue actif de la sélection, voir
    # agentAffichage/selection/catalogue.py) :
    "image": registre.image,
    "table": registre.tableau,
    "code": registre.code,
    "file": registre.fichier,
    "card": registre.carte,
    "chart": registre.graphique,
    "stats": registre.statistiques,
    "timeline": registre.chronologie,
    # Composants de base et widget météo : plus proposés par la sélection
    # actuelle, mais toujours utilisables à la main (mode "Agent (Rendu
    # Direct)" du sandbox) — rien n'est supprimé côté rendu.
    "weather": registre.carte_meteo,
    "titre": lambda data: registre.titre(data.get("texte", ""), data.get("niveau", 2)),
    "paragraphe": lambda data: registre.paragraphe(data.get("texte", "")),
    "liste": lambda data: registre.liste(data.get("items", []), data.get("ordonnee", False)),
}


def _widget_erreur(message: str, contenu_brut: str) -> str:
    """Fallback dégradé : si un widget ne peut pas être rendu, on affiche l'erreur + le contenu brut."""
    return (
        '<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;'
        'padding:10px 14px;margin:12px 0;font-size:13px;color:#991B1B;">'
        f'⚠️ {html.escape(message)}'
        f'<pre style="margin-top:6px;font-size:11px;white-space:pre-wrap;color:#7F1D1D;">'
        f'{html.escape(contenu_brut)}</pre>'
        '</div>'
    )


def _extraire_widgets(texte: str) -> Tuple[str, Dict[str, str]]:
    """
    Retire du texte les blocs ```widget:<type>...```, les rend via le registre,
    et les remplace par des marqueurs uniques pour ne pas perturber le parsing
    Markdown du reste du texte.

    Returns:
        (texte_sans_widgets, {marqueur: html_du_widget})
    """
    widgets: Dict[str, str] = {}

    def _remplacer(match: re.Match) -> str:
        marqueur = f"@@WIDGET_{len(widgets)}@@"
        type_widget = match.group(1)
        payload_brut = match.group(2)

        fonction = _REGISTRE_WIDGETS.get(type_widget)
        if fonction is None:
            widgets[marqueur] = _widget_erreur(f"Composant inconnu : « {type_widget} »", payload_brut)
            return marqueur

        try:
            data = json.loads(payload_brut)
            widgets[marqueur] = fonction(data)
        except Exception:
            widgets[marqueur] = _widget_erreur(f"Données invalides pour « {type_widget} »", payload_brut)

        return marqueur

    return _WIDGET_BLOCK_RE.sub(_remplacer, texte), widgets


def _injecter_widgets(html_rendu: str, widgets: Dict[str, str]) -> str:
    for marqueur, widget_html in widgets.items():
        # Markdown place un marqueur isolé sur sa propre ligne dans un <p>.
        motif_paragraphe = f"<p>{marqueur}</p>"
        if motif_paragraphe in html_rendu:
            html_rendu = html_rendu.replace(motif_paragraphe, widget_html)
        else:
            html_rendu = html_rendu.replace(marqueur, widget_html)
    return html_rendu


def afficherJoliment(texte: str, fichiers: Optional[List] = None) -> str:
    """
    Transforme le texte et les fichiers en un affichage HTML/CSS/JS.

    Le texte est interprété comme du Markdown (généré naturellement 
    par Mistral dans ses réponses.
    Les blocs ```widget:<type> sont extraits avant le parsing Markdown et
    rendus séparément via le registre de composants (agentAffichage/rendu/registre.py).

    Args:
        texte: Le texte à afficher (Markdown, avec blocs widget optionnels).
        fichiers: Liste de fichiers uploadés (avec .name et .getvalue()).

    Returns:
        Code HTML/CSS/JS autonome (sera rendu dans un moteur Chromium isolé).
    """
    try:
        texte_sans_widgets, widgets = _extraire_widgets(texte)
        content_html = md.markdown(texte_sans_widgets, extensions=_MD_EXTENSIONS)
        content_html = _injecter_widgets(content_html, widgets)
    except Exception:
        # Fallback dégradé : texte brut échappé si le parsing échoue.
        content_html = f'<div class="content-raw">{html.escape(texte)}</div>'

    escaped_source = html.escape(texte)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Inter', Helvetica Neue, Helvetica, Arial, sans-serif;
    padding: 2px;
    color: #1a1a1a;
    background: transparent;
  }}
  .card {{
    background: #ffffff;
    border: 1px solid #E8E2DB;
    border-radius: 14px;
    padding: 18px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  }}

  .content {{ font-size: 15.5px; line-height: 1.68; color: #292524; }}
  .content-raw {{ font-size: 15px; line-height: 1.6; white-space: pre-wrap; }}

  .content > *:first-child {{ margin-top: 0; }}
  .content > *:last-child {{ margin-bottom: 0; }}

  .content p {{ margin: 10px 0; }}

  .content h1, .content h2, .content h3, .content h4 {{
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1.3;
  }}
  .content h1 {{
    font-size: 24px;
    letter-spacing: -0.02em;
    margin: 4px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #E8E2DB;
  }}
  .content h2 {{
    font-size: 13px;
    font-variant: small-caps;
    letter-spacing: 0.05em;
    color: {pal.VERT_FONCE};
    margin: 20px 0 8px;
  }}
  .content h3 {{
    font-size: 16px;
    color: #44403C;
    margin: 16px 0 6px;
  }}
  .content h4 {{
    font-size: 14.5px;
    color: #57534E;
    margin: 14px 0 4px;
  }}

  .content strong {{ font-weight: 700; color: #1a1a1a; }}
  .content em {{ font-style: italic; color: #44403C; }}

  .content ul, .content ol {{ margin: 8px 0 10px; padding-left: 22px; }}
  .content li {{ margin: 4px 0; }}
  .content ul li::marker {{ color: {pal.VERT}; }}
  .content ol li::marker {{ color: {pal.VERT}; font-weight: 600; }}

  .content blockquote {{
    margin: 10px 0;
    padding: 4px 14px;
    border-left: 3px solid {pal.VERT};
    background: {pal.FOND_DOUX};
    color: {pal.TEXTE_MUTED};
    font-style: italic;
    border-radius: 0 8px 8px 0;
  }}

  .content code {{
    font-family: Monaco, Menlo, monospace;
    font-size: 0.88em;
    background: #F5F0EB;
    border: 1px solid #E8E2DB;
    border-radius: 5px;
    padding: 1px 5px;
  }}
  .content pre {{
    margin: 10px 0;
    padding: 12px 14px;
    background: #F5F0EB;
    border: 1px solid #E8E2DB;
    border-radius: 10px;
    overflow-x: auto;
  }}
  .content pre code {{
    background: none;
    border: none;
    padding: 0;
    font-size: 12.5px;
    color: #44403C;
  }}

  .content a {{ color: {pal.VERT}; text-decoration: none; border-bottom: 1px solid {pal.VERT_CLAIR}; }}
  .content a:hover {{ color: {pal.VERT_FONCE}; border-bottom-color: {pal.VERT}; }}

  .content hr {{ border: none; border-top: 1px solid #E8E2DB; margin: 16px 0; }}

  .content table {{ border-collapse: collapse; margin: 10px 0; width: 100%; font-size: 14px; }}
  .content th, .content td {{ border: 1px solid #E8E2DB; padding: 6px 10px; text-align: left; }}
  .content th {{ background: #F5F0EB; font-weight: 600; }}

  details {{ margin-top: 12px; padding-top: 10px; border-top: 1px solid #E8E2DB; }}
  summary {{ cursor: pointer; font-size: 12px; font-weight: 500; color: #A8A29E; user-select: none; outline: none; }}
  summary:hover {{ color: #78716C; }}
  details pre {{ margin-top: 10px; padding: 12px; background: #F5F0EB; border: 1px solid #E8E2DB; border-radius: 10px; overflow-x: auto; font-size: 12px; color: #44403C; font-family: Monaco, Menlo, monospace; white-space: pre-wrap; word-break: break-all; }}
</style>
</head>
<body>
<div class="card">
  <div class="content">{content_html}</div>
  <details>
    <summary>Voir le texte source (Markdown)</summary>
    <pre><code>{escaped_source}</code></pre>
  </details>
</div>
</body>
</html>"""
