#!/usr/bin/env python3
"""
Vérification manuelle de selectionner_widget() avec un vrai appel Mistral.
Nécessite MISTRAL_API_KEY dans l'environnement. Ne fait pas partie de la suite
de tests automatisée (tests/test_selecteur_phase2.py la simule, sans réseau).

Lancement : .venv/bin/python3 verifier_selection.py
"""

import sys

from agentAffichage.selection.selecteur import selectionner_widget

EXEMPLES = [
    # Négatif attendu : une seule valeur, déjà claire en une phrase.
    "La température extérieure est de 15°C.",
    # Positif attendu : CHART (ligne) — une série temporelle.
    "Les températures seront de 15°C lundi, 18°C mardi, 21°C mercredi et 17°C jeudi.",
    # Négatif attendu : une seule valeur isolée.
    "La population de Paris est d'environ 2,1 millions d'habitants.",
    # Positif attendu : CHART (barres) — comparaison entre entités.
    "Population : Paris 2,1M, Marseille 0,9M, Lyon 0,5M, Toulouse 0,5M.",
    # Négatif attendu : une seule information, pas de CARD.
    "Paris est la capitale de la France.",
    # Positif attendu : CARD — plusieurs attributs d'une même entité.
    "Apple Inc. a été fondée en 1976. Son siège social est à Cupertino, en Californie. Son PDG est Tim Cook.",
    # Positif attendu : STATS — plusieurs indicateurs clés.
    "Chiffre d'affaires : 420 M€. Croissance : +12%. Marge : 24%. Employés : 4 200.",
    # Positif attendu : TIMELINE — séquence chronologique.
    "1976 : Fondation d'Apple. 1984 : Lancement du Macintosh. 2007 : Présentation de l'iPhone.",
    # Positif attendu : IMAGE — une URL d'image explicite.
    "Voici un aperçu du logo : ![Logo](https://exemple.com/logo.png)",
    # Négatif attendu : image mentionnée sans URL utilisable, ne pas inventer.
    "Voici une photo de la tour Eiffel de nuit.",
    # Positif attendu : FILE — un lien de téléchargement réel.
    "Voici le rapport annuel : [Télécharger](https://exemple.com/rapport-annuel.pdf)",
    # Positif attendu : CODE — un vrai bloc de code.
    "Voici comment inverser une liste en Python :\n\n```python\ndef inverser(liste):\n    return liste[::-1]\n```",
    # Négatif attendu : petit tableau, le Markdown suffit déjà.
    "| Ville | Population |\n|---|---|\n| Paris | 2,1M |\n| Lyon | 0,5M |",
]


def main() -> int:
    for texte in EXEMPLES:
        print(f"\n--- Texte : {texte!r}")
        try:
            resultat = selectionner_widget(texte)
        except Exception as exc:
            print(f"Échec : {exc}")
            continue
        print(resultat.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
