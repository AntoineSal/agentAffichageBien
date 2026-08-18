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
logique de sélection, et inversement. `pipeline.py::genererAffichage()` est le
seul point d'entrée qui enchaîne les deux étages ; c'est lui que `sandbox/app.py`
appelle en mode *"Utilisateur (API Mistral)"*.

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
├── verifier_selection.py       vérification manuelle avec un vrai appel Mistral (clé requise)
├── tests/
│   ├── test_selection_phase1.py   catalogue → prompt → schémas, sans appel API
│   ├── test_selecteur_phase2.py    selecteur.py avec un client Mistral simulé, sans appel API
│   └── test_pipeline_phase3.py      genererAffichage() : succès, "aucun", et repli sur échec
└── agentAffichage/
    ├── README.md              ce document
    ├── pipeline.py             genererAffichage() : sélection puis rendu, avec repli
    ├── rendu/
    │   ├── afficheur.py         afficherJoliment() : Markdown + blocs widget → HTML
    │   └── registre.py           composants HTML purs (un par widget)
    └── selection/
        ├── schemas.py            modèles Pydantic (ResultatSelection, DonneesWeather...)
        ├── catalogue.py           liste déclarative des widgets connus
        ├── prompt.py               génère le prompt de sélection depuis le catalogue
        └── selecteur.py            selectionner_widget() : appel Mistral (SDK mistralai)
```

## Catalogue des widgets

| Widget | Statut | Schéma | Rendu |
|---|---|---|---|
| `weather` | bout en bout, branché dans le sandbox (mode "Utilisateur (API Mistral)") | `selection/schemas.py::DonneesWeather` | `registre.carte_meteo()` |
| `lien`, `photo`, `calendrier`, `carte` | ciblés pour la v1, ordre et contenu à préciser en phase 4 | à créer | à créer |

`weather` est un widget pilote : c'est le seul déjà validé côté rendu, donc celui
sur lequel le mécanisme de sélection a été prouvé en premier avant d'être
dupliqué aux autres (phase 4).

## Les trois modes du sandbox

`sandbox/app.py` propose trois modes (boutons radio dans la barre latérale), qui
ne font pas tourner les mêmes étages de la pipeline :

| Mode | Ce qui tourne | Ce que le champ de saisie représente |
|---|---|---|
| **Utilisateur (API Mistral)** | conversation → sélection → rendu | une question posée à Mistral |
| **Texte brut (Sélection + Rendu)** | sélection → rendu (pas de conversation) | le texte brut tel qu'il sortirait déjà de Mistral — on se branche directement à l'entrée de la pipeline |
| **Agent (Rendu Direct)** | rendu seul | la réponse déjà formatée, avec un bloc `` ```widget:type{json}``` `` écrit à la main si besoin |

Le mode **"Texte brut (Sélection + Rendu)"** est le plus utile pour tester la
sélection sur des cas construits à la main (météo complète, partielle, absente,
hors sujet...) sans dépendre de ce que le vrai Mistral (sans outil météo) est
capable de répondre — collez-y directement un texte plausible et regardez si le
bon widget apparaît, avec les bonnes données.

## Appeler Mistral pour de vrai

`selectionner_widget()` lit la clé API via son paramètre `api_key`, ou sinon la
variable d'environnement `MISTRAL_API_KEY` (même convention que
`sandbox/utils.py::call_mistral_api`). Pour tester `selectionner_widget()` seule,
sans passer par le sandbox :

```bash
export MISTRAL_API_KEY="votre_clé"
export PYTHONUTF8=1
.venv/bin/python3 verifier_selection.py
```

`PYTHONUTF8=1` est nécessaire si votre shell n'exporte pas `LANG`/`LC_ALL` (cas
constaté le 17/08/2026) : sans ça, une bibliothèque de la chaîne d'appel Mistral
échoue avec une `UnicodeEncodeError` cryptique dès que le prompt de sélection
contient un caractère accentué. `selectionner_widget()` détecte ce cas et lève
une erreur claire plutôt que de laisser planter l'appel sans explication.

Note : `.env`/`.env.example` existent dans le repo mais ne sont chargés
automatiquement par aucun code actuellement (pas de `python-dotenv`) — seule la
variable d'environnement exportée, ou le champ "Clé API Mistral" du sandbox,
fonctionnent réellement aujourd'hui (les deux sont lus par `genererAffichage()`
via `pipeline.py`, exactement comme `selectionner_widget()` seul).

## État d'avancement

- [x] **Phase 0** — rangement physique (`rendu/` + `selection/`), ce document
- [x] **Phase 0bis** — réécriture de `carte_meteo()` : plus de valeurs de repli, widgets extensibles (voir convention ci-dessus)
- [x] **Phase 1** — fondations de la sélection sans appel LLM : `schemas.py`, `catalogue.py`, `prompt.py`, testés par `tests/test_selection_phase1.py`
- [x] **Phase 2** — `selecteur.py` écrit, testé (client Mistral simulé), et vérifié avec un vrai appel Mistral (`verifier_selection.py`, 17/08/2026)
- [x] **Phase 3** — `pipeline.py::genererAffichage()` + branchement dans `sandbox/app.py`, fallback testé. Trois modes dans le sandbox (voir "Les trois modes du sandbox" ci-dessus) ; "Agent (Rendu Direct)" continue d'appeler `afficherJoliment()` directement
- [ ] **Phase 4** — extension aux widgets suivants
- [ ] **Phase 5** — robustesse (grille de test manuelle)
- [ ] **Phase 6** — bilan avec Antoine

