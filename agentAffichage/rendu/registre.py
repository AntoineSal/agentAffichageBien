"""
Registre de composants d'affichage.

Chaque fonction transforme des données Python simples en un fragment HTML/CSS.
"""

import datetime
import html
from typing import Dict, List, Optional


# ─── Composants de base  ────────────────────────────────────────────────────

def titre(texte: str, niveau: int = 2) -> str:
    niveau = min(max(niveau, 1), 4)
    tag = f"h{niveau}"
    styles = {
        1: "font-size:24px;font-weight:700;letter-spacing:-0.02em;color:#1a1a1a;"
           "margin:4px 0 12px;padding-bottom:8px;border-bottom:1px solid #E8E2DB;",
        2: "font-size:13px;font-weight:700;font-variant:small-caps;letter-spacing:0.05em;"
           "color:#B45309;margin:20px 0 8px;",
        3: "font-size:16px;font-weight:700;color:#44403C;margin:16px 0 6px;",
        4: "font-size:14.5px;font-weight:700;color:#57534E;margin:14px 0 4px;",
    }
    return f'<{tag} style="{styles[niveau]}">{html.escape(texte)}</{tag}>'


def paragraphe(texte: str) -> str:
    return (
        '<p style="margin:10px 0;font-size:15.5px;line-height:1.68;color:#292524;">'
        f'{html.escape(texte)}</p>'
    )


def liste(items: List[str], ordonnee: bool = False) -> str:
    tag = "ol" if ordonnee else "ul"
    puces = "".join(
        f'<li style="margin:4px 0;">{html.escape(str(item))}</li>' for item in items
    )
    return f'<{tag} style="margin:8px 0 10px;padding-left:22px;">{puces}</{tag}>'


# ─── Composant riche : carte météo ──────────────────────────────────────────

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
    Attend le format renvoyé par le tool get_weather (open_meteo) du backend :
    {"location": str, "current": {...}, "forecast_3_days": [...]}
    """
    location = data.get("location", "Lieu inconnu")
    current = data.get("current", {})
    forecast = data.get("forecast_3_days", [])

    condition = current.get("condition", "")
    temperature = current.get("temperature", "?")

    details = [
        f"Ressenti {v}" if k == "apparent_temperature" else
        f"Vent {v}" if k == "wind_speed" else
        f"Humidité {v}"
        for k, v in current.items()
        if k in ("apparent_temperature", "wind_speed", "humidity") and v
    ]
    details_html = " · ".join(html.escape(d) for d in details)

    cases_prevision = "".join(
        f'''<div style="flex:1;text-align:center;padding:10px 6px;background:#FBF7F2;
                border-radius:10px;border:1px solid #E8E2DB;">
              <div style="font-size:11px;font-weight:600;color:#A8A29E;text-transform:uppercase;
                    letter-spacing:0.04em;">{html.escape(_jour_court(jour.get("date", "")))}</div>
              <div style="font-size:22px;margin:4px 0;">{_icone_meteo(jour.get("condition", ""))}</div>
              <div style="font-size:13px;color:#1a1a1a;font-weight:600;">{html.escape(jour.get("temp_max", "?"))}</div>
              <div style="font-size:12px;color:#A8A29E;">{html.escape(jour.get("temp_min", "?"))}</div>
            </div>'''
        for jour in forecast[:3]
    )

    return f'''
    <div style="background:linear-gradient(135deg,#FEF3E2,#FBF7F2);border:1px solid #F0D9B5;
          border-radius:16px;padding:20px;margin:12px 0;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <div style="font-size:13px;font-weight:600;color:#B45309;text-transform:uppercase;
                letter-spacing:0.05em;">{html.escape(location)}</div>
          <div style="font-size:36px;font-weight:700;color:#1a1a1a;margin-top:4px;">{html.escape(temperature)}</div>
          <div style="font-size:14px;color:#57534E;margin-top:2px;">{html.escape(condition)}</div>
          {f'<div style="font-size:12px;color:#78716C;margin-top:6px;">{details_html}</div>' if details_html else ''}
        </div>
        <div style="font-size:56px;">{_icone_meteo(condition)}</div>
      </div>
      {f'<div style="display:flex;gap:8px;margin-top:16px;">{cases_prevision}</div>' if cases_prevision else ''}
    </div>'''
