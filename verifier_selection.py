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
    "Bien sûr ! Voici la météo à Paris : il fait actuellement 18°C avec une pluie légère.",
    "La capitale de la France est Paris, une ville de plus de 2 millions d'habitants.",
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
