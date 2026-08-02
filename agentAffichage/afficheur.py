"""
Module principal pour l'agent d'affichage (à implémenter par le stagiaire).

La fonction afficherJoliment reçoit un texte et des fichiers,
et doit retourner un code HTML/CSS/JS autonome.
"""

from typing import List, Optional
import html


def afficherJoliment(texte: str, fichiers: Optional[List] = None) -> str:
    """
    Transforme le texte et les fichiers en un affichage HTML/CSS/JS.

    Args:
        texte: Le texte à afficher.
        fichiers: Liste de fichiers uploadés (avec .name et .getvalue()).

    Returns:
        Code HTML/CSS/JS autonome (sera rendu dans un moteur Chromium isolé).
    """
    escaped_texte = html.escape(texte)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: Helvetica Neue, Helvetica, Arial, sans-serif; padding: 2px; color: #1a1a1a; background: transparent; }}
  .card {{ background: #ffffff; border: 1px solid #E8E2DB; border-radius: 14px; padding: 18px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }}
  .content {{ line-height: 1.6; font-size: 15px; white-space: pre-wrap; }}
  details {{ margin-top: 12px; padding-top: 10px; border-top: 1px solid #E8E2DB; }}
  summary {{ cursor: pointer; font-size: 12px; font-weight: 500; color: #A8A29E; user-select: none; outline: none; }}
  summary:hover {{ color: #78716C; }}
  pre {{ margin-top: 10px; padding: 12px; background: #F5F0EB; border: 1px solid #E8E2DB; border-radius: 10px; overflow-x: auto; font-size: 12px; color: #44403C; font-family: Monaco, Menlo, monospace; white-space: pre-wrap; word-break: break-all; }}
</style>
</head>
<body>
<div class="card">
  <div class="content">{texte}</div>
  <details>
    <summary>Voir le code HTML</summary>
    <pre><code>{escaped_texte}</code></pre>
  </details>
</div>
</body>
</html>"""
