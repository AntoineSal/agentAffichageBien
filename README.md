# Sandbox Agent Affichage

Application Desktop pour tester la fonction `afficherJoliment`.

## Lancement

```bash
pip3 install -r requirements.txt
python3 main.py
```

## Objectif du Stagiaire

Implémenter la fonction `afficherJoliment(texte, fichiers)` dans `agentAffichage/afficheur.py`.

Cette fonction reçoit un texte et des fichiers, et doit retourner du code **HTML/CSS/JS autonome** (`<!DOCTYPE html>...`).

Le rendu est affiché dans un moteur Chromium isolé (QWebEngineView) — vous pouvez utiliser des CDN externes (Chart.js, Leaflet, D3.js, etc.).
