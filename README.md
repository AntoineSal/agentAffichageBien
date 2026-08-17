# Sandbox Agent Affichage

Application Desktop pour tester la fonction `afficherJoliment`.

## Lancement

```bash
pip3 install -r requirements.txt
python3 main.py
```

## Objectif du projet

Implémenter la fonction `afficherJoliment(texte, fichiers)` dans `agentAffichage/rendu/afficheur.py`.

Le fonctionnement détaillé de la pipeline (sélection puis rendu) est documenté dans [`agentAffichage/README.md`](agentAffichage/README.md).

Cette fonction reçoit un texte et des fichiers, et doit retourner du code **HTML/CSS/JS autonome** (`<!DOCTYPE html>...`).

Le rendu est affiché dans un moteur Chromium isolé (QWebEngineView) avec possibilité d'utiliser des CDN externes.
