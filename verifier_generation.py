#!/usr/bin/env python3
"""
Vérification manuelle du NOUVEAU flux (génération + outils d'affichage) avec de
vrais appels Mistral. Pendant de verifier_selection.py, qui teste l'ancien.

Nécessite MISTRAL_API_KEY dans l'environnement. Ne fait pas partie de la suite
de tests automatisée (tests/test_generation_outils.py la simule, sans réseau).

Lancement : PYTHONUTF8=1 .venv/bin/python3 verifier_generation.py
"""

import sys

from agentAffichage.generation.generateur import generer_avec_outils

# Ce sont des QUESTIONS d'utilisateur, pas des réponses déjà rédigées : dans
# cette architecture, c'est le modèle générateur qui écrit la réponse ET décide
# des widgets. La comparaison avec verifier_selection.py se fait donc sur
# l'intention, pas sur un texte d'entrée identique.
QUESTIONS = [
    # Attendu : aucun widget — une phrase suffit.
    "En une phrase, quelle est la capitale de la France ?",
    # Attendu : aucun widget — valeur unique, déjà claire en toutes lettres.
    "En une phrase, quelle est la population de Paris ?",
    # Attendu : plutôt un chart — série de valeurs comparables.
    "Donne-moi la population des 5 plus grandes villes françaises.",
    # Attendu : plutôt une card — entité à plusieurs attributs.
    "Présente-moi brièvement l'entreprise Tesla : fondation, siège, PDG.",
    # Attendu : plutôt une timeline — séquence chronologique.
    "Quelles sont les grandes étapes de l'histoire d'Apple ?",
    # Attendu : plutôt un chart (évolution) — série temporelle.
    "Comment la population mondiale a-t-elle évolué de 1950 à 2020, par décennie ?",
    # Attendu : aucun widget — question conversationnelle.
    "Explique-moi en deux phrases ce qu'est le machine learning.",
]


def main() -> int:
    for question in QUESTIONS:
        print(f"\n{'=' * 70}\n QUESTION : {question}")
        try:
            resultat = generer_avec_outils(question)
        except Exception as exc:
            print(f" Échec : {exc}")
            continue

        if resultat.metriques:
            m = resultat.metriques
            print(f" [{m.temps_appel_ms:.0f} ms · {m.tokens_total or '?'} tokens]")

        print(f"\n--- Markdown ({len(resultat.markdown)} caractères) ---")
        print(resultat.markdown[:600])

        if resultat.widgets:
            print(f"\n--- Widgets appelés : {len(resultat.widgets)} ---")
            for widget in resultat.widgets:
                print(f"  [{widget.type}] {widget.donnees.model_dump_json(exclude_none=True)[:220]}")
        else:
            print("\n--- Aucun widget appelé ---")

        if resultat.invalides:
            print(f"\n--- Tool calls ignorés : {len(resultat.invalides)} ---")
            for invalide in resultat.invalides:
                print(f"  [{invalide.nom_outil}] {invalide.erreur}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
