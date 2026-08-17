# Pipeline d'affichage — sélection + rendu

Ce document explique le fonctionnement interne du module `agentAffichage`. Pour
lancer l'application de test, voir le [README à la racine](../README.md).

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
{"location": "Paris", "current": {"temperature": "18°C", "condition": "Pluie légère"}, "forecast": [...]}
​```
```

Ce format est stable et ne change pas au fil des phases suivantes.

### Convention : widgets extensibles, jamais de valeur de repli

Chaque widget accepte volontairement plus de champs que ce qu'un texte donné en
remplira en général (ex : `forecast` peut contenir n'importe quel nombre de jours,
pas seulement 3). Mais si une donnée n'est pas présente dans le texte source, la
ligne correspondante **disparaît du rendu** — elle n'affiche jamais de valeur de
repli comme `"?"` ou `"Lieu inconnu"`. `rendu/registre.py` factorise ce principe
dans deux utilitaires partagés, `_fragment()` et `_joindre_fragments()`, pensés
pour être réutilisés par les prochains widgets plutôt que réécrits à chaque fois.

## Structure des fichiers

```
agentAffichageBien/
├── tests/
│   └── test_selection_phase1.py   catalogue → prompt → schémas, sans appel API
└── agentAffichage/
    ├── README.md              ce document
    ├── pipeline.py             (à venir, phase 3) orchestrateur bout-en-bout
    ├── rendu/
    │   ├── afficheur.py         afficherJoliment() : Markdown + blocs widget → HTML
    │   └── registre.py           composants HTML purs (un par widget)
    └── selection/
        ├── schemas.py            modèles Pydantic (ResultatSelection, DonneesWeather...)
        ├── catalogue.py           liste déclarative des widgets connus
        ├── prompt.py               génère le prompt de sélection depuis le catalogue
        └── selecteur.py            (à venir, phase 2) appel Mistral de sélection
```

## Catalogue des widgets

| Widget | Statut | Schéma | Rendu |
|---|---|---|---|
| `weather` | schéma prêt, appel Mistral à brancher (phase 2) | `selection/schemas.py::DonneesWeather` | `registre.carte_meteo()` |
| `lien`, `photo`, `calendrier`, `carte` | ciblés pour la v1, ordre et contenu à préciser en phase 4 | à créer | à créer |

`weather` est un widget pilote : c'est le seul déjà validé côté rendu, donc celui
sur lequel le mécanisme de sélection sera prouvé en premier avant d'être dupliqué
aux autres.

## État d'avancement

- [x] **Phase 0** — rangement physique (`rendu/` + `selection/`), ce document
- [x] **Phase 0bis** — réécriture de `carte_meteo()` : plus de valeurs de repli, widgets extensibles (voir convention ci-dessus)
- [x] **Phase 1** — fondations de la sélection sans appel LLM : `schemas.py`, `catalogue.py`, `prompt.py`, testés par `tests/test_selection_phase1.py`
- [ ] **Phase 2** — premier appel Mistral réel, widget `weather` seul (`selecteur.py`)
- [ ] **Phase 3** — orchestrateur `pipeline.py` + branchement dans le sandbox, avec fallback
- [ ] **Phase 4** — extension aux widgets suivants
- [ ] **Phase 5** — robustesse (grille de test manuelle)
- [ ] **Phase 6** — bilan avec Antoine

