"""
Registre de composants d'affichage.

Chaque fonction transforme des données Python simples en un fragment HTML/CSS.
Toutes les couleurs viennent de palette.py (source de vérité partagée avec
sandbox/app.py) — jamais de couleur écrite en dur ici.
"""

import datetime
import html
import json
import uuid
from typing import Dict, List, Optional

from . import palette as pal


# ─── Composants de base  ────────────────────────────────────────────────────

def titre(texte: str, niveau: int = 2) -> str:
    niveau = min(max(niveau, 1), 4)
    tag = f"h{niveau}"
    styles = {
        1: f"font-size:24px;font-weight:700;letter-spacing:-0.02em;color:{pal.TEXTE};"
           f"margin:4px 0 12px;padding-bottom:8px;border-bottom:1px solid {pal.BORDURE};",
        2: f"font-size:13px;font-weight:700;font-variant:small-caps;letter-spacing:0.05em;"
           f"color:{pal.VERT_FONCE};margin:20px 0 8px;",
        3: f"font-size:16px;font-weight:700;color:{pal.TEXTE_MUTED};margin:16px 0 6px;",
        4: f"font-size:14.5px;font-weight:700;color:{pal.TEXTE_MUTED};margin:14px 0 4px;",
    }
    return f'<{tag} style="{styles[niveau]}">{html.escape(texte)}</{tag}>'


def paragraphe(texte: str) -> str:
    return (
        f'<p style="margin:10px 0;font-size:15.5px;line-height:1.68;color:{pal.TEXTE};">'
        f'{html.escape(texte)}</p>'
    )


def liste(items: List[str], ordonnee: bool = False) -> str:
    tag = "ol" if ordonnee else "ul"
    puces = "".join(
        f'<li style="margin:4px 0;">{html.escape(str(item))}</li>' for item in items
    )
    return f'<{tag} style="margin:8px 0 10px;padding-left:22px;">{puces}</{tag}>'


# ─── Utilitaires partagés ───────────────────────────────────────────────────
# Convention pour tous les widgets : une donnée absente ne produit ni valeur de
# repli ("?", "Lieu inconnu") ni ligne vide — la ligne disparaît. Ces deux
# fonctions factorisent ce principe pour que les prochains widgets n'aient pas
# à le réécrire à la main à chaque fois.

def _fragment(label: str, valeur: Optional[str]) -> str:
    """'Label valeur' si valeur est présente, sinon une chaîne vide."""
    return f"{label} {valeur}" if valeur else ""


def _joindre_fragments(*fragments: str, separateur: str = " · ") -> str:
    """Assemble les fragments non vides (voir _fragment) dans l'ordre donné."""
    return separateur.join(html.escape(f) for f in fragments if f)


# ─── Composant riche : carte météo ──────────────────────────────────────────
# Retiré du catalogue actif de la sélection (voir agentAffichage/README.md) —
# toujours utilisable à la main (mode "Agent (Rendu Direct)" du sandbox).

_ICONES_METEO = [
    (("orage",), "⛈️"),
    (("neige",), "❄️"),
    (("pluie", "bruine", "averse"), "🌧️"),
    (("brouillard",), "🌫️"),
    (("couvert", "nuageux"), "☁️"),
    (("dégagé", "degage"), "☀️"),
]


def _icone_meteo(condition: str) -> str:
    c = condition.lower()
    for mots_cles, icone in _ICONES_METEO:
        if any(mot in c for mot in mots_cles):
            return icone
    return "🌤️"


def _jour_court(date_iso: str) -> str:
    jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    try:
        return jours[datetime.date.fromisoformat(date_iso).weekday()]
    except (ValueError, TypeError):
        return date_iso[:10]


def carte_meteo(data: Dict) -> str:
    """
    Composant météo : chaque ligne n'apparaît que si la donnée correspondante est
    présente dans data. Un texte source partiel (ex: seulement une température)
    produit un widget partiel — jamais de valeur de repli ("?", "Lieu inconnu").

    Champs attendus, tous optionnels sauf mention contraire :
      {"location": str,
       "current": {"temperature": str, "condition": str, "apparent_temperature": str,
                    "wind_speed": str, "humidity": str},
       "forecast": [{"date": str, "condition": str, "temp_max": str, "temp_min": str}]}

    "date" est la seule clé obligatoire au sein d'un jour de forecast (un jour sans
    date ne peut pas être affiché). forecast n'est pas limité à 3 éléments : on
    affiche autant de jours que fournis, d'où le renommage depuis forecast_3_days.
    """
    location = data.get("location")
    current = data.get("current") or {}
    forecast = data.get("forecast") or []

    condition = current.get("condition")
    temperature = current.get("temperature")

    details_html = _joindre_fragments(
        _fragment("Ressenti", current.get("apparent_temperature")),
        _fragment("Vent", current.get("wind_speed")),
        _fragment("Humidité", current.get("humidity")),
    )

    entete_html = "".join(filter(None, [
        f'<div style="font-size:13px;font-weight:600;color:{pal.VERT_FONCE};text-transform:uppercase;'
        f'letter-spacing:0.05em;">{html.escape(location)}</div>' if location else "",
        f'<div style="font-size:36px;font-weight:700;color:{pal.TEXTE};margin-top:4px;">'
        f'{html.escape(temperature)}</div>' if temperature else "",
        f'<div style="font-size:14px;color:{pal.TEXTE_MUTED};margin-top:2px;">'
        f'{html.escape(condition)}</div>' if condition else "",
        f'<div style="font-size:12px;color:{pal.TEXTE_MUTED};margin-top:6px;">{details_html}</div>'
        if details_html else "",
    ]))
    icone_html = f'<div style="font-size:56px;">{_icone_meteo(condition)}</div>' if condition else ""

    cases_prevision = "".join(
        f'''<div style="flex:0 0 64px;text-align:center;padding:10px 6px;background:{pal.FOND_DOUX};
                border-radius:10px;border:1px solid {pal.BORDURE};">
              <div style="font-size:11px;font-weight:600;color:{pal.TEXTE_FAINT};text-transform:uppercase;
                    letter-spacing:0.04em;">{html.escape(_jour_court(jour["date"]))}</div>
              {f'<div style="font-size:22px;margin:4px 0;">{_icone_meteo(jour["condition"])}</div>' if jour.get("condition") else ""}
              {f'<div style="font-size:13px;color:{pal.TEXTE};font-weight:600;">{html.escape(jour["temp_max"])}</div>' if jour.get("temp_max") else ""}
              {f'<div style="font-size:12px;color:{pal.TEXTE_FAINT};">{html.escape(jour["temp_min"])}</div>' if jour.get("temp_min") else ""}
            </div>'''
        for jour in forecast
        if jour.get("date")
    )

    return f'''
    <div style="background:linear-gradient(135deg,{pal.VERT_CLAIR},{pal.FOND_DOUX});border:1px solid {pal.BORDURE};
          border-radius:16px;padding:20px;margin:12px 0;">
      {f'<div style="display:flex;align-items:center;justify-content:space-between;"><div>{entete_html}</div>{icone_html}</div>' if (entete_html or icone_html) else ''}
      {f'<div style="display:flex;gap:8px;margin-top:16px;overflow-x:auto;">{cases_prevision}</div>' if cases_prevision else ''}
    </div>'''


# ─── Composant : IMAGE ───────────────────────────────────────────────────────

def image(data: Dict) -> str:
    url = data.get("url")
    if not url:
        return ""
    pied = _joindre_fragments(data.get("legende") or "", _fragment("Source :", data.get("source")))
    id_erreur = f"img-err-{uuid.uuid4().hex[:8]}"
    return f'''
    <figure style="margin:12px 0;border:1px solid {pal.BORDURE};border-radius:14px;overflow:hidden;background:{pal.SURFACE};">
      <img src="{html.escape(url)}" alt="{html.escape(data.get("alt", ""))}"
           style="display:block;width:100%;max-height:420px;object-fit:cover;"
           onerror="this.style.display='none';document.getElementById('{id_erreur}').style.display='block';">
      <div id="{id_erreur}" style="display:none;padding:16px;font-size:13px;color:{pal.TEXTE_MUTED};">⚠️ Image indisponible (URL inaccessible depuis le rendu)</div>
      {f'<figcaption style="padding:10px 14px;font-size:13px;color:{pal.TEXTE_MUTED};">{pied}</figcaption>' if pied else ''}
    </figure>'''


# ─── Composant : TABLE ───────────────────────────────────────────────────────

def tableau(data: Dict) -> str:
    colonnes = data.get("colonnes") or []
    if not colonnes:
        return ""
    lignes = data.get("lignes") or []
    titre_tbl = data.get("titre")
    entetes = "".join(
        f'<th style="text-align:left;padding:8px 12px;font-size:11px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.04em;color:{pal.TEXTE_FAINT};background:{pal.FOND_DOUX};'
        f'border-bottom:1px solid {pal.BORDURE};position:sticky;top:0;">{html.escape(c)}</th>'
        for c in colonnes
    )
    corps = "".join(
        "<tr>" + "".join(
            f'<td style="padding:8px 12px;font-size:13.5px;color:{pal.TEXTE};'
            f'border-bottom:1px solid {pal.BORDURE};">{html.escape(str(cellule))}</td>'
            for cellule in ligne
        ) + "</tr>"
        for ligne in lignes
    )
    return f'''
    <div style="margin:12px 0;">
      {f'<div style="font-size:13px;font-weight:600;color:{pal.VERT_FONCE};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">{html.escape(titre_tbl)}</div>' if titre_tbl else ''}
      <div style="border:1px solid {pal.BORDURE};border-radius:12px;overflow:auto;max-height:360px;">
        <table style="border-collapse:collapse;width:100%;">
          <thead><tr>{entetes}</tr></thead>
          <tbody>{corps}</tbody>
        </table>
      </div>
    </div>'''


# ─── Composant : CODE (coloration syntaxique via highlight.js, CDN) ─────────

def code(data: Dict) -> str:
    contenu = data.get("code")
    if not contenu:
        return ""
    langage = (data.get("langage") or "").lower()
    titre_bloc = data.get("titre")
    classe_langage = f"language-{langage}" if langage else ""
    id_bloc = f"code-{uuid.uuid4().hex[:8]}"
    return f'''
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-light.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <div style="margin:12px 0;border:1px solid {pal.BORDURE};border-radius:12px;overflow:hidden;">
      {f'<div style="padding:8px 14px;background:{pal.FOND_DOUX};font-size:12px;font-weight:600;color:{pal.TEXTE_MUTED};border-bottom:1px solid {pal.BORDURE};">{html.escape(titre_bloc)}</div>' if titre_bloc else ''}
      <pre style="margin:0;padding:14px;overflow-x:auto;background:{pal.SURFACE};"><code id="{id_bloc}" class="{classe_langage}">{html.escape(contenu)}</code></pre>
    </div>
    <script>
      (function() {{
        var essayer = function() {{
          if (window.hljs) {{ hljs.highlightElement(document.getElementById("{id_bloc}")); }}
          else {{ setTimeout(essayer, 50); }}
        }};
        essayer();
      }})();
    </script>'''


# ─── Composant : FILE ────────────────────────────────────────────────────────

_ICONES_FICHIER = {
    "pdf": "📄", "docx": "📝", "doc": "📝", "xlsx": "📊", "xls": "📊",
    "pptx": "📽️", "ppt": "📽️", "csv": "📊", "zip": "🗜️", "txt": "📃",
}


def _extension(url: str) -> str:
    nom = url.rsplit("/", 1)[-1]
    return nom.rsplit(".", 1)[-1].lower() if "." in nom else ""


def fichier(data: Dict) -> str:
    url = data.get("url")
    if not url:
        return ""
    ext = (data.get("type_fichier") or _extension(url)).lower()
    icone = _ICONES_FICHIER.get(ext, "📎")
    nom = data.get("nom") or url.rsplit("/", 1)[-1]
    sous_texte = _joindre_fragments(ext.upper() if ext else "", data.get("taille") or "")
    return f'''
    <a href="{html.escape(url)}" target="_blank" rel="noopener" style="display:flex;align-items:center;
          gap:12px;text-decoration:none;background:{pal.FOND_DOUX};border:1px solid {pal.BORDURE};border-radius:12px;
          padding:12px 16px;margin:12px 0;">
      <div style="font-size:28px;">{icone}</div>
      <div>
        <div style="font-size:14px;font-weight:600;color:{pal.TEXTE};">{html.escape(nom)}</div>
        {f'<div style="font-size:12px;color:{pal.TEXTE_MUTED};margin-top:2px;">{sous_texte}</div>' if sous_texte else ''}
      </div>
    </a>'''


# ─── Composant : CARD ────────────────────────────────────────────────────────

def carte(data: Dict) -> str:
    titre_carte = data.get("titre")
    if not titre_carte:
        return ""
    sous_titre = data.get("sous_titre")
    lignes = "".join(
        f'''<div style="display:flex;justify-content:space-between;gap:12px;padding:7px 0;
                border-bottom:1px solid {pal.BORDURE};">
              <span style="font-size:13px;color:{pal.TEXTE_MUTED};">{html.escape(a.get("label", ""))}</span>
              <span style="font-size:13px;font-weight:600;color:{pal.TEXTE};text-align:right;">{html.escape(str(a.get("valeur", "")))}</span>
            </div>'''
        for a in (data.get("attributs") or [])
        if a.get("label") and a.get("valeur") is not None
    )
    return f'''
    <div style="margin:12px 0;padding:18px 20px;background:{pal.SURFACE};border:1px solid {pal.BORDURE};border-radius:14px;">
      <div style="font-size:17px;font-weight:700;color:{pal.TEXTE};">{html.escape(titre_carte)}</div>
      {f'<div style="font-size:13px;color:{pal.TEXTE_FAINT};margin-top:2px;">{html.escape(sous_titre)}</div>' if sous_titre else ''}
      {f'<div style="margin-top:12px;">{lignes}</div>' if lignes else ''}
    </div>'''


# ─── Composant : CHART (via Chart.js, CDN) ───────────────────────────────────

_TYPE_CHARTJS = {"ligne": "line", "barres": "bar", "secteurs": "pie", "nuage_points": "scatter"}


def _couleur_serie(i: int) -> str:
    return pal.SERIE_GRAPHIQUE[i % len(pal.SERIE_GRAPHIQUE)]


def graphique(data: Dict) -> str:
    type_graphique = data.get("type_graphique")
    series = data.get("series") or []
    if not type_graphique or not series:
        return ""
    type_js = _TYPE_CHARTJS.get(type_graphique, "bar")

    if type_js == "pie":
        # Un camembert n'a qu'une série, mais CHAQUE PART doit recevoir sa
        # propre couleur : une seule couleur pour tout le dataset donnerait un
        # disque uni (bug initialement rapporté).
        valeurs = series[0].get("valeurs", [])
        datasets = [{
            "label": series[0].get("nom") or "",
            "data": valeurs,
            "backgroundColor": [_couleur_serie(i) for i in range(len(valeurs))],
            "borderColor": pal.SURFACE,
            "borderWidth": 2,
        }]
        afficher_legende = True
    else:
        datasets = [
            {
                "label": s.get("nom") or f"Série {i + 1}",
                "data": s.get("valeurs", []),
                "borderColor": _couleur_serie(i),
                "backgroundColor": _couleur_serie(i) if type_js == "bar" else "transparent",
            }
            for i, s in enumerate(series)
        ]
        afficher_legende = len(datasets) > 1

    config = {
        "type": type_js,
        "data": {"labels": data.get("categories") or [], "datasets": datasets},
        "options": {"responsive": True, "plugins": {"legend": {"display": afficher_legende}}},
    }
    id_graph = f"chart-{uuid.uuid4().hex[:8]}"
    titre_graph = data.get("titre")
    return f'''
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <div style="margin:12px 0;padding:16px;border:1px solid {pal.BORDURE};border-radius:14px;background:{pal.SURFACE};">
      {f'<div style="font-size:13px;font-weight:600;color:{pal.VERT_FONCE};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;">{html.escape(titre_graph)}</div>' if titre_graph else ''}
      <canvas id="{id_graph}" style="max-height:280px;"></canvas>
    </div>
    <script>
      (function() {{
        var essayer = function() {{
          if (window.Chart) {{ new Chart(document.getElementById("{id_graph}"), {json.dumps(config)}); }}
          else {{ setTimeout(essayer, 50); }}
        }};
        essayer();
      }})();
    </script>'''


# ─── Composant : STATS ───────────────────────────────────────────────────────

def statistiques(data: Dict) -> str:
    cases = "".join(
        f'''<div style="flex:1;min-width:120px;padding:14px;background:{pal.FOND_DOUX};
                border:1px solid {pal.BORDURE};border-radius:12px;">
              <div style="font-size:11px;font-weight:600;color:{pal.TEXTE_FAINT};text-transform:uppercase;
                    letter-spacing:0.04em;">{html.escape(ind.get("label", ""))}</div>
              <div style="font-size:24px;font-weight:700;color:{pal.TEXTE};margin-top:4px;">{html.escape(str(ind.get("valeur", "")))}</div>
              {f'<div style="font-size:12px;color:{pal.VERT_FONCE};margin-top:2px;font-weight:600;">{html.escape(ind["tendance"])}</div>' if ind.get("tendance") else ''}
            </div>'''
        for ind in (data.get("indicateurs") or [])
        if ind.get("label") and ind.get("valeur") is not None
    )
    if not cases:
        return ""
    titre_stats = data.get("titre")
    return f'''
    <div style="margin:12px 0;">
      {f'<div style="font-size:13px;font-weight:600;color:{pal.VERT_FONCE};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;">{html.escape(titre_stats)}</div>' if titre_stats else ''}
      <div style="display:flex;gap:10px;flex-wrap:wrap;">{cases}</div>
    </div>'''


# ─── Composant : TIMELINE ────────────────────────────────────────────────────

def chronologie(data: Dict) -> str:
    evenements = [e for e in (data.get("evenements") or []) if e.get("date") and e.get("titre")]
    if not evenements:
        return ""
    titre_tl = data.get("titre")
    items = "".join(
        f'''<div style="position:relative;padding:0 0 18px 22px;border-left:2px solid {pal.BORDURE};">
              <div style="position:absolute;left:-6px;top:2px;width:10px;height:10px;
                    border-radius:50%;background:{pal.VERT};"></div>
              <div style="font-size:11px;font-weight:600;color:{pal.VERT_FONCE};text-transform:uppercase;
                    letter-spacing:0.04em;">{html.escape(e["date"])}</div>
              <div style="font-size:14px;font-weight:600;color:{pal.TEXTE};margin-top:2px;">{html.escape(e["titre"])}</div>
              {f'<div style="font-size:13px;color:{pal.TEXTE_MUTED};margin-top:2px;">{html.escape(e["description"])}</div>' if e.get("description") else ''}
            </div>'''
        for e in evenements
    )
    return f'''
    <div style="margin:12px 0;">
      {f'<div style="font-size:13px;font-weight:600;color:{pal.VERT_FONCE};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:12px;">{html.escape(titre_tl)}</div>' if titre_tl else ''}
      <div style="margin-left:4px;">{items}</div>
    </div>'''
