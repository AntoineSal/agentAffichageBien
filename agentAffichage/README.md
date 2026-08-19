# Pipeline d'affichage — sélection + rendu

Ce document explique le fonctionnement interne du module `agentAffichage`. Pour
lancer l'application de test, voir le [README à la racine](../README.md).

## Objectif

Transformer la réponse brute de Mistral (Markdown naturel, sans connaissance des
widgets) en un affichage HTML enrichi, quand un widget apporte une valeur
substantiellement meilleure que le Markdown seul — jamais parce que le contenu
correspond juste techniquement au format d'un widget (voir "Philosophie" plus
bas). Le module est découpé en deux étages indépendants, qui ne communiquent
que par du texte.

## Architecture en deux étages

```
texte brut (Mistral)
        │
        ▼
┌───────────────────┐   décide QUOI afficher : 0, 1 ou plusieurs widgets,
│     sélection      │   et extrait les données depuis le texte
└───────────────────┘
        │
        ▼
texte annoté (même texte + 0 à 3 blocs ```widget:type{json}```)
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
d'origine, avec 0 à 3 blocs en plus (souvent 0), dans le format que
`rendu/afficheur.py` sait déjà parser — et qui accepte nativement plusieurs
blocs dans un même texte, sans rien y changer :

```
Chiffre d'affaires : 420 M€. Croissance : +12%. Marge : 24%. Employés : 4 200.

​```widget:stats
{"indicateurs": [{"label": "Chiffre d'affaires", "valeur": "420 M€", "tendance": "+12%"}, ...]}
​```
```

Ce format est stable et ne change pas selon le catalogue de widgets actif.

### Convention : widgets extensibles, jamais de valeur de repli

Chaque widget accepte volontairement plus de champs que ce qu'un texte donné en
remplira en général (ex : `forecast` peut contenir n'importe quel nombre de jours,
pas seulement 3). Mais si une donnée n'est pas présente dans le texte source, la
ligne correspondante **disparaît du rendu** — elle n'affiche jamais de valeur de
repli comme `"?"` ou `"Lieu inconnu"`. `rendu/registre.py` factorise ce principe
dans deux utilitaires partagés, `_fragment()` et `_joindre_fragments()`, pensés
pour être réutilisés par les prochains widgets plutôt que réécrits à chaque fois.

### Palette de couleurs

`rendu/palette.py` est la seule source de couleurs : les 8 fonctions de rendu,
la CSS de page (`afficheur.py`) et l'UI PySide6 du sandbox (`sandbox/app.py`)
l'importent toutes les trois — jamais de couleur écrite en dur ailleurs.

Couleur de marque EchoSocial (fournie par l'utilisateur) :
`ECHO_COLOR = dynamicColor("rgba(10, 145, 104, 0.8)", "rgba(22, 185, 134, 0.85)")`
— le sandbox n'ayant qu'un thème clair, `VERT` reprend la variante claire telle
quelle (`#0A9168`), `VERT_VIF` réutilise la variante sombre comme accent (`#16B986`).

| Constante | Rôle |
|---|---|
| `VERT` / `VERT_FONCE` / `VERT_PRESSE` / `VERT_CLAIR` / `VERT_VIF` | couleur de marque et ses variations |
| `AMBRE`, `BLEU`, `PRUNE`, `CORAIL` | complémentaires, calculées à luminosité/saturation proches du vert |
| `SERIE_GRAPHIQUE` | rotation des 6 couleurs ci-dessus pour les graphiques multi-séries et les camemberts |
| `TEXTE`, `TEXTE_MUTED`, `TEXTE_FAINT`, `SURFACE`, `FOND_DOUX`, `BORDURE` | neutres, repris tels quels (déjà neutres, s'accordent avec le vert) |

**Bug corrigé (18/08/2026)** : les camemberts affichaient toutes leurs parts
dans la même couleur. Cause : Chart.js attend un *tableau* de couleurs
(`backgroundColor`) pour un graphique en secteurs — une part par valeur — alors
que le code appliquait une seule couleur par *série* (correct pour barres/lignes,
mais un camembert n'a qu'une série). `graphique()` traite maintenant les
graphiques `secteurs` différemment : `_couleur_serie(i)` par valeur, pas par série.

## Structure des fichiers

```
agentAffichageBien/
├── verifier_selection.py         vérification manuelle avec un vrai appel Mistral (clé requise)
├── exemples_test_sandbox.txt     réponses simulées à coller en mode "Texte brut (Sélection + Rendu)"
├── tests/
│   ├── test_selection_phase1.py     catalogue (8 widgets) → prompt → schémas, sans appel API
│   ├── test_selecteur_phase2.py      selecteur.py avec un client Mistral simulé, sans appel API
│   ├── test_confiance.py              filtrage par seuil de confiance
│   ├── test_pipeline_phase3.py         genererAffichage() : filtrage + rendu + repli sur échec
│   └── test_registre_widgets.py         les 8 fonctions de rendu, palette, couleurs du camembert
└── agentAffichage/
    ├── README.md              ce document
    ├── pipeline.py             genererAffichage() : sélection, filtrage, rendu, avec repli
    ├── rendu/
    │   ├── palette.py            couleurs partagées (widgets + UI du sandbox), source unique
    │   ├── afficheur.py           afficherJoliment() : Markdown + blocs widget(s) → HTML
    │   └── registre.py             composants HTML purs (un par widget)
    └── selection/
        ├── schemas.py            modèles Pydantic (union discriminée, candidats + confidence)
        ├── catalogue.py           liste déclarative des 8 widgets connus (objectif/quand/quand pas)
        ├── prompt.py               génère le prompt (widgets + score de confiance) depuis le catalogue
        ├── confiance.py             SEUIL_AFFICHAGE + filtrage déterministe des candidats
        └── selecteur.py             selectionner_widget() : appel Mistral (SDK mistralai)
```

## Philosophie

Contrainte de départ : l'agent conversationnel qui produit le Markdown **n'est
jamais modifié** et ignore l'existence des widgets — la sélection ne dispose
que du texte Markdown déjà écrit comme entrée. Elle ne doit jamais inventer une
information absente de ce texte.

Règle centrale, plus importante que tout le reste : **un widget ne doit être
créé que s'il apporte une valeur substantiellement meilleure que le Markdown**,
jamais parce que le contenu correspond juste techniquement à un format de
widget. Les faux positifs sont pires que les faux négatifs — une réponse sans
aucun widget est souvent le bon résultat.

Exemple qui résume tout : *"La température extérieure est de 15°C."* ne doit
**pas** générer de widget (la phrase suffit). *"Les températures seront de
15°C lundi, 18°C mardi, 21°C mercredi et 17°C jeudi."* **peut** justifier un
graphique (`chart`), parce que l'évolution devient nettement plus lisible.

Le texte complet du prompt (avec les 12 étapes de la démarche de décision) est
généré par `selection/prompt.py::construire_prompt_selection()` — à lire
directement plutôt que dupliqué ici, pour ne jamais diverger de ce que Mistral
reçoit réellement.

### Score de confiance

Depuis le 18/08/2026, chaque widget candidat porte son propre `confidence`
(0 à 1) et sa `raison`, calculés par Mistral selon 5 dimensions pondérées :
pertinence (25%), complétude (20%), **valeur ajoutée (35%, la plus
importante)**, clarté (10%), redondance (10%). Le modèle **n'applique lui-même
aucun seuil** : `ResultatSelection.candidats` contient tous les candidats
évalués, même ceux jugés faibles — c'est `selection/confiance.py::widgets_retenus()`
qui filtre ensuite, de façon déterministe, avec `SEUIL_AFFICHAGE = 0.75` (bande
"bonne pertinence" de la spec fournie par l'utilisateur, volontairement élevée :
on préfère un widget manqué à un widget inutile affiché).

Garder ce seuil dans du code Python plutôt que dans le prompt le rend ajustable
sans re-toucher au prompt, et garder tous les candidats (pas seulement les
retenus) rend les rejets inspectables — utile pour le futur outil de debug
évoqué plus bas.

Le bloc `` ```widget:type{json}``` `` (voir "Le contrat" ci-dessus) ne contient
que `donnees` — `confidence`/`raison` ne sont jamais sérialisés dans le texte
affiché, ils ne servent qu'en interne à la décision.

## Catalogue des widgets

Liste fermée à 8 widgets génériques (pas de widget spécifique à un domaine
comme la météo ou le calendrier — n'importe quel domaine se représente via
l'un de ces 8 types structurels) :

| Widget | Rôle | Déclencheur typique |
|---|---|---|
| `image` | image déjà référencée par une URL utilisable | image Markdown ou URL directe |
| `table` | tableau interactif (tri/filtre/recherche) | tableau volumineux, pas un petit tableau Markdown |
| `code` | visionneuse de code (coloration syntaxique) | un vrai bloc de code, pas un fragment inline |
| `file` | fichier téléchargeable référencé | lien Markdown vers un PDF/DOCX/XLSX/CSV/ZIP... |
| `card` | entité avec plusieurs attributs distincts | personne, entreprise, produit, lieu... décrits en détail |
| `chart` | série temporelle ou comparaison entre entités | plusieurs valeurs comparables, pas un chiffre isolé |
| `stats` | quelques indicateurs numériques clés | KPI, plusieurs mesures ensemble |
| `timeline` | séquence chronologique d'événements distincts | plusieurs dates formant une progression |

Détail complet (objectif, quand l'utiliser, quand surtout pas, exemples
positifs/négatifs) dans `selection/catalogue.py`.

**Note sur `weather`** : retiré du catalogue actif (il n'appartient pas à la
liste fermée des 8 types) suite à un retour direct de l'utilisateur sur des
problèmes non encore résolus avec ce widget. `registre.carte_meteo()` et son
entrée de dispatch dans `afficheur.py` restent en place, inchangés — un bloc
`` ```widget:weather{...}``` `` écrit à la main (mode "Agent (Rendu Direct)")
continue de fonctionner. Rien n'est supprimé, juste plus proposé par la
sélection en l'état actuel.

### Widget `image` : pourquoi une URL peut ne rien afficher

Deux causes possibles si une vraie URL de photo ne montre rien :
1. **L'URL pointe vers une page web, pas vers le fichier image lui-même**
   (ex : un lien Unsplash/Pinterest/Google Images vers la *page* de la photo,
   pas vers son fichier `.jpg`/`.png`). Un `<img src="...">` a besoin du lien
   direct vers le fichier. Depuis le 18/08/2026, ce cas affiche maintenant un
   message "⚠️ Image indisponible" au lieu de rien du tout (`onerror` sur la
   balise `<img>`, voir `registre.image()`).
2. **Le texte de test contenait l'URL nue**, pas la syntaxe Markdown
   `![description](url)`. Avec une URL nue, le Markdown ne rend pas l'image
   nativement — elle reste visible en texte brut à côté du widget (voulu :
   voir "La réponse Markdown d'origine reste la source de vérité" plus haut,
   le texte doit rester compréhensible même si le widget échoue). Pour que
   *seule* la photo apparaisse, sans lien texte visible, écrire le test avec
   la syntaxe Markdown `![...](...)` : le Markdown natif l'affiche déjà comme
   une image, indépendamment du widget.

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
- [x] **Refonte (18/08/2026)** — catalogue remplacé par les 8 widgets génériques (IMAGE/TABLE/CODE/FILE/CARD/CHART/STATS/TIMELINE) sur spec détaillée de l'utilisateur, remplace l'approche par domaine (weather/lien/photo/calendrier/carte) prévue en phase 4. Sélection multi-widgets (0 à 3 par réponse). `weather` retiré du catalogue actif, code de rendu conservé.
- [x] **Score de confiance (18/08/2026)** — chaque candidat porte confidence + raison (5 dimensions pondérées), filtrage déterministe par seuil (`selection/confiance.py`, `SEUIL_AFFICHAGE = 0.75`). Le modèle ne filtre plus lui-même.
- [x] **Palette + corrections visuelles (18/08/2026)** — `rendu/palette.py` (vert de marque EchoSocial + complémentaires), appliquée aux 8 widgets, à la CSS de page et à l'UI du sandbox. Bug des camemberts monochromes corrigé. Widget `image` : repli visible si l'URL est cassée.
- [x] **56/56 tests passent** (schémas, catalogue, prompt, confiance, sélecteur simulé, pipeline, rendu). **Toujours pas vérifié avec un vrai appel Mistral** — candidats à confidence + union discriminée dans une liste est un terrain encore plus nouveau pour les Custom Structured Outputs qu'avant ; à tester en conditions réelles avant de considérer le mécanisme fiable.
- [ ] **Demandé, pas encore fait** — une "console" dans le sandbox montrant, pour chaque message passé par la sélection, tous les candidats évalués et leur confidence (utile pour ajuster le prompt à la main). Discuté en réponse, pas implémenté.
- [ ] **Phase 5** — robustesse (grille de test manuelle) sur le nouveau catalogue
- [ ] **Phase 6** — bilan avec Antoine

