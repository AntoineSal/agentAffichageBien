"""
Palette de couleurs partagée par tous les widgets (rendu/registre.py) et par
l'interface du sandbox (sandbox/app.py) — une seule source de vérité, pour
que les deux ne divergent jamais.

Couleur de marque EchoSocial (fournie par l'utilisateur) :
  ECHO_COLOR = dynamicColor(
      "rgba(10, 145, 104, 0.8)",   # clair
      "rgba(22, 185, 134, 0.85)",  # sombre
  )
Le sandbox n'a qu'un thème clair : VERT reprend la variante claire telle
quelle ; VERT_VIF réutilise la variante sombre comme accent plus vif (survol,
mise en avant), plutôt que d'inventer une troisième teinte.
"""

# ─── Vert (couleur de marque, base de la palette) ────────────────────────────
VERT = "#0A9168"
VERT_FONCE = "#06583F"
VERT_PRESSE = "#04402E"
VERT_CLAIR = "#E8F3EF"
VERT_VIF = "#16B986"

# ─── Couleurs complémentaires ────────────────────────────────────────────────
# Choisies à luminosité/saturation proches du vert pour qu'aucune ne domine
# visuellement les autres dans un graphique multi-séries.
AMBRE = "#D48D11"
BLEU = "#3067A6"
PRUNE = "#72428A"
CORAIL = "#D2532D"

# Ordre de rotation pour les séries de graphique et les parts de camembert —
# chaque élément doit recevoir une couleur différente de ses voisins directs.
SERIE_GRAPHIQUE = [VERT, AMBRE, BLEU, PRUNE, CORAIL, VERT_VIF]

# ─── Neutres ──────────────────────────────────────────────────────────────
# Un fond crème neutre s'accorde bien avec un vert de marque saturé — repris
# tel quel plutôt que réinventé, pour ne pas risquer une régression visuelle
# non vérifiable sans capture d'écran de l'appli.
TEXTE = "#1A1A1A"
TEXTE_MUTED = "#57534E"
TEXTE_FAINT = "#A8A29E"
SURFACE = "#FFFFFF"
FOND_DOUX = "#FBF7F2"
BORDURE = "#E8E2DB"
