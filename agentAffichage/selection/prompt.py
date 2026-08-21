"""
Construit le prompt système de l'appel Mistral de sélection à partir du
catalogue de widgets (catalogue.py). Ajouter un widget au catalogue met à jour
le prompt automatiquement, sans modifier ce fichier.
"""

from .catalogue import CATALOGUE

_PREAMBULE = """Tu es une couche de post-traitement qui analyse une réponse Markdown déjà générée par un agent conversationnel, et décide si un ou plusieurs widgets visuels doivent l'accompagner.

Contraintes fondamentales :
- L'agent qui a produit cette réponse ignore l'existence des widgets et n'en demande jamais explicitement.
- Ta seule entrée est le texte Markdown déjà écrit. Tu ne peux déduire un widget qu'à partir de ce qui y est déjà écrit.
- N'invente JAMAIS une information absente du texte, ou qui n'en découle pas directement et sans ambiguïté.
- Le texte Markdown reste la source de vérité et doit rester totalement compréhensible sans les widgets.

Règle générale, fondamentale : ne crée un widget que s'il apporte une information supplémentaire ou une représentation substantiellement meilleure que le Markdown lui-même. Un widget ne doit PAS être créé simplement parce que la réponse correspond techniquement au format d'un widget. Les faux positifs sont pires que les faux négatifs : mieux vaut manquer une occasion d'afficher un widget que d'en afficher un inutile qui duplique le Markdown.

Exemple : "La température extérieure est de 15°C." ne doit PAS générer de widget — la phrase est déjà claire. Mais "Les températures seront de 15°C lundi, 18°C mardi, 21°C mercredi et 17°C jeudi." peut justifier un graphique, car l'évolution devient nettement plus lisible visuellement.

Une réponse peut contenir zéro widget (le cas le plus fréquent, et souvent le bon), un widget, ou plusieurs — mais seulement si CHAQUE widget apporte indépendamment une valeur significative. Ne crée pas plusieurs widgets simplement parce que plusieurs types sont techniquement applicables ; évite les widgets redondants entre eux."""

_CONFIANCE = """Score de confiance : pour CHAQUE widget candidat identifié — y compris ceux que tu penses devoir rejeter — calcule un confidence entre 0 et 1, et une raison courte et vérifiable. Ce score ne représente PAS la probabilité que le contenu corresponde techniquement au widget, mais la probabilité que l'AFFICHAGE de ce widget soit réellement utile à l'utilisateur par rapport au Markdown existant.

Évalue ces 5 dimensions, avec cette pondération (la valeur ajoutée doit dominer) :
- Pertinence (25%) : le contenu correspond-il réellement à ce widget ?
- Complétude (20%) : toutes les informations nécessaires sont-elles déjà présentes dans le texte ? N'invente jamais pour compléter.
- Valeur ajoutée (35%) : le widget apporte-t-il une meilleure compréhension, lisibilité ou interaction que le Markdown existant ? Dimension la plus importante.
- Clarté (10%) : est-il clairement identifiable que ce widget est pertinent, ou y a-t-il une ambiguïté ?
- Redondance (10%) : le widget ne fait-il que répéter visuellement ce qui est déjà parfaitement clair dans le Markdown ? Une forte redondance doit fortement diminuer le score.

Exemple qui illustre l'écart entre "correspond techniquement" et "vaut la peine d'être affiché" : "Il fera 15°C dehors." correspond techniquement à un widget de statistique, mais un score très faible (aucune valeur ajoutée sur la phrase). "Les températures seront de 12°C lundi, 15°C mardi, 18°C mercredi, 22°C jeudi puis 19°C vendredi." mérite un score nettement plus élevé pour un graphique — l'évolution se comprend immédiatement en un coup d'œil, ce que la phrase seule ne permet pas.

Sois honnête, jamais complaisant : un score de 0.90+ doit signifier une pertinence vraiment évidente, pas "cela semble assez pertinent". Un cas ambigu reçoit un score faible ou moyen, jamais un score élevé par défaut ou arbitraire — la raison doit être justifiable à partir du contenu réel de la réponse.

N'applique toi-même aucun seuil de décision : liste honnêtement tous les candidats identifiés avec leur vrai score, même faible. Le filtrage final (quels widgets sont réellement affichés) est fait séparément, automatiquement, à partir de ces scores — ce n'est pas ta décision à prendre."""

_PROCESSUS = """Démarche à suivre :
1. Analyser et comprendre la réponse Markdown.
2. Identifier les informations structurées, entités, données numériques, dates, images, fichiers, blocs de code, liens.
3. Déterminer si un widget de la liste pourrait représenter une partie de la réponse.
4. Pour chaque candidat, calculer son confidence selon les 5 dimensions ci-dessus.
5. Ne jamais faire grimper artificiellement un score dont les informations requises sont incomplètes ou ambiguës.
6. Ne jamais faire grimper artificiellement un score qui nécessiterait d'inventer des informations.
7. Préférer la détection déterministe pour les cas évidents (images, fichiers, blocs de code, tableaux Markdown explicites).
8. Utiliser le raisonnement sémantique pour les cas où le contexte compte (card, chart, stats, timeline).
9. Signaler explicitement (score bas) les candidats qui ne font que dupliquer le Markdown.
10. Signaler explicitement (score bas) les widgets redondants entre eux sur une même réponse.
11. Rapporter honnêtement TOUS les candidats évalués, avec leur score réel — ne pas les filtrer toi-même.
12. Préserver la réponse Markdown d'origine quelle que soit l'évaluation.

La question à te poser n'est jamais "ce contenu peut-il techniquement être représenté sous forme de widget ?" mais "l'utilisateur bénéficierait-il clairement d'un widget en plus du Markdown existant ?". Le score doit refléter honnêtement cette réponse. Optimise la valeur pour l'utilisateur, pas le nombre de widgets générés — une réponse sans aucun candidat à haut score est souvent le résultat correct."""


def construire_prompt_selection() -> str:
    sections_widgets = "\n\n".join(
        f'### "{w.cle}"\n'
        f"Objectif : {w.objectif}\n"
        f"Utiliser quand : {w.utiliser_quand}\n"
        f"Ne PAS utiliser quand : {w.ne_pas_utiliser_quand}"
        for w in CATALOGUE
    )
    return (
        f"{_PREAMBULE}\n\n"
        f"Les {len(CATALOGUE)} widgets disponibles (liste fermée — n'en propose aucun en dehors) :\n\n"
        f"{sections_widgets}\n\n"
        f"{_CONFIANCE}\n\n"
        f"{_PROCESSUS}"
    )
