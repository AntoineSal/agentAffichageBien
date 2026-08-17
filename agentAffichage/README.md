# Pipeline d'affichage — sélection + rendu

Ce document explique le fonctionnement interne du module `agentAffichage`.
. Pour lancer l'application de test, voir le [README à la racine](../README.md).

## Objectif

Transformer la réponse brute de Mistral (Markdown naturel, sans connaissance des
widgets) en un affichage HTML enrichi, quand un widget peut apporter quelque chose
visuellement (météo, lien, photo...). Le module est découpé en deux étages
indépendants, qui ne communiquent que par du texte.

## Architecture en deux étages

```
texte brut (Mistral)
        │
        ▼
┌───────────────────┐   décide QUOI afficher : quel widget (ou aucun),
│     sélection      │   et extrait les données depuis le texte
└───────────────────┘
        │
        ▼
texte annoté (même texte + au plus un bloc ```widget:type{json}```)
        │
        ▼
┌───────────────────┐   décide COMMENT l'afficher : Markdown → HTML,
│       rendu         │   composants du registre → HTML
└───────────────────┘
        │
        ▼
      HTML/CSS autonome
```

- **`selection/`** — reçoit le texte brut, fait un appel Mistral dédié (séparé de la
  conversation avec l'utilisateur) à sortie structurée, et décide si un widget du
  catalogue s'applique. Il ne peut extraire que ce qui est déjà écrit dans le
  texte — jamais inventer une donnée absente.
- **`rendu/`** — reçoit le texte (annoté ou non) et le transforme en HTML. Contient
  la fonction `afficherJoliment` et le registre de composants. Ne sait rien de
  *comment* un widget a été choisi, seulement comment l'afficher.

Cette séparation permet de modifier l'apparence d'un widget sans toucher à la
logique de sélection, et inversement.

## Le contrat entre les deux étages

La sélection ne retourne jamais de HTML ni d'objet Python, seulement le texte
d'origine, avec au plus un bloc en plus, dans le format que `rendu/afficheur.py`
sait déjà parser :

```
Bien sûr ! Voici les prévisions pour Paris : il fait 18°C, pluie légère...

​```widget:weather
{"location": "Paris", "current": {"temperature": "18°C", "condition": "Pluie légère"}, "forecast_3_days": [...]}
​```
```

Ce format est stable et ne change pas au fil des phases suivantes.

## Structure des fichiers

```
agentAffichage/
├── README.md              ce document
├── pipeline.py             (à venir, phase 3) orchestrateur bout-en-bout
├── rendu/
│   ├── afficheur.py         afficherJoliment() : Markdown + blocs widget → HTML
│   └── registre.py           composants HTML purs (un par widget)
└── selection/
    ├── catalogue.py          (à venir, phase 1) widgets connus
    ├── schemas.py             (à venir, phase 1) modèles de données par widget
    ├── prompt.py               (à venir, phase 1) prompt de sélection
    └── selecteur.py             (à venir, phase 2) appel Mistral de sélection
```

## Catalogue des widgets

| Widget | Statut | Rendu |
|---|---|---|
| `weather` | rendu fait, sélection à brancher | `registre.carte_meteo()` |
| `lien`, `photo`, `calendrier`, `carte` | ciblés pour la v1, ordre et contenu à préciser en phase 4 | à créer |

`weather` est un widget pilote : c'est le seul déjà validé côté rendu, donc celui
sur lequel le mécanisme de sélection sera prouvé en premier avant d'être dupliqué
aux autres.

