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

## Nouvelle architecture : widgets décidés à la génération (`generation/`)

Depuis le 20/08/2026, **un second flux coexiste** avec celui décrit ci-dessus,
pour pouvoir comparer les deux sur les mêmes requêtes. L'ancien reste
entièrement fonctionnel et inchangé.

```
ANCIEN     question → Mistral #1 (texte) → Mistral #2 (sélection) → filtre confiance → rendu
NOUVEAU    question → Mistral unique (texte + tool calls d'affichage) ──────────────→ rendu
```

Dans le nouveau flux, l'agent qui **répond** à l'utilisateur connaît lui-même
les widgets et décide, pendant la génération, d'en appeler ou non. Il voit donc
la question et tout le contexte — ce que le juge de l'ancien flux n'a jamais
(il ne relit que le texte final).

### Ce sont des outils d'affichage, pas des outils fonctionnels

Les 8 widgets sont déclarés à Mistral via son mécanisme de *function calling*,
mais **aucune boucle d'exécution n'a lieu** : un tool call n'est jamais exécuté,
ne renvoie aucun résultat au modèle, et ne déclenche jamais de second appel.
**Le tool call EST le résultat** — une spécification de widget qui part
directement au renderer.

### Ce qui garantit qu'un widget est valide

| Garantie | Mécanisme |
|---|---|
| JSON invalide | impossible : les arguments sont structurés par l'API, et un JSON illisible est écarté à la validation |
| Widget inexistant | impossible : seuls les 8 outils déclarés existent, et `cle_depuis_nom_outil()` rejette tout nom inconnu |
| Champ inventé | `additionalProperties: false` posé récursivement sur chaque schéma (helper `rec_strict_json_schema` du SDK, déjà utilisé par l'ancien flux) |
| Paramètres invalides | validation Pydantic des arguments contre le modèle `Donnees*` à la réception |
| Bloc mal fermé / mélange au Markdown | n'existe pas : `content` et `tool_calls` sont deux canaux séparés de la réponse |

La garantie réelle est la **validation Pydantic à la réception** : elle ne
dépend pas du comportement exact de l'API, et un widget refusé est simplement
écarté — le Markdown n'est jamais affecté.

### Réutilisation de l'existant

Rien n'est dupliqué. Le nouveau flux réutilise :
`selection/schemas.py` (les modèles `Donnees*` servent de schéma d'arguments des
outils), `selection/catalogue.py` (les descriptions des outils en sont
générées), `pipeline.py::_construire_blocs_widgets()`, `rendu/registre.py`,
`rendu/afficheur.py`, `afficherJoliment()` — tous inchangés.

Le partage de `_construire_blocs_widgets()` entre les deux flux repose sur le
`Protocol` `PorteurWidget` : `WidgetCandidat` (ancien) et `WidgetGenere`
(nouveau) exposent tous deux `.type` et `.donnees`, et c'est tout ce dont la
sérialisation a besoin — aucun des deux flux n'a besoin de connaître l'autre.

### Pas de score de confiance ici — volontairement

`WidgetGenere` ne porte ni `confidence` ni `raison`. Dans cette architecture,
c'est le modèle générateur qui décide d'appeler un outil : il n'y a plus de
second juge à qui demander une note, donc rien à filtrer ensuite. La retenue
est obtenue par le prompt et les descriptions d'outils, pas par un seuil. Un
score ne sera réintroduit que si les tests montrent une surproduction réelle de
widgets.

### Placement des widgets dans la réponse

Les blocs sont ajoutés **à la fin** du texte, comme dans l'ancien flux. Le
renderer place chaque widget là où son bloc apparaît : il n'a besoin d'aucune
information de position pour fonctionner, donc l'architecture la plus simple
suffit.

Un placement intégré au corps du message (card en tête, image là où le texte en
parle) **est demandé** depuis le 24/08/2026. Étude de faisabilité et plan
d'implémentation : `FEUILLE_DE_ROUTE_WIDGETS_INTEGRES.md` à la racine du dépôt.

Point vérifié le 24/08/2026, utile à connaître avant d'y toucher : le renderer
place déjà correctement un widget en tête ou intercalé entre deux paragraphes —
c'est une conséquence directe du système de marqueurs de `_extraire_widgets()`
/ `_injecter_widgets()`. **`rendu/` n'a donc pas à bouger** ; tout le sujet tient
dans `pipeline.py::_annoter_texte()`, qui décide où poser les blocs.

### Streaming — état vérifié

Vérifié par introspection du SDK installé (`mistralai` 2.9.3), pas supposé :
`client.chat.stream()` existe, et `DeltaMessage` porte bien **à la fois**
`content` et `tool_calls` (une liste de `ToolCall`, chacun avec un champ `index`
prévu pour recoller des arguments fragmentés sur plusieurs chunks). Le streaming
est donc **structurellement compatible** avec cette architecture, et c'est un
argument en sa faveur : le texte peut s'afficher pendant que les arguments des
widgets arrivent encore — ce qu'une sortie structurée sur toute la réponse ne
permettrait pas.

Il n'est volontairement **pas implémenté** pour l'instant, pour deux raisons
factuelles : le sandbox affiche aujourd'hui chaque message d'un coup
(`setHtml` sur un `QWebEngineView`, aucun rendu incrémental à alimenter), et le
comportement réel du modèle en streaming (fragmentation des arguments, ordre
d'arrivée, tool calls multiples) n'a pas pu être observé sur un vrai appel. Une
version non streamée propre est livrée d'abord, plutôt qu'un faux streaming qui
accumulerait les chunks pour tout afficher à la fin.

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
├── verifier_selection.py         ANCIEN flux, vrai appel Mistral (clé requise)
├── verifier_generation.py        NOUVEAU flux, vrai appel Mistral (clé requise)
├── exemples_test_sandbox.txt     réponses simulées à coller en mode "Texte brut (Sélection + Rendu)"
├── tests/
│   ├── test_selection_phase1.py     catalogue (8 widgets) → prompt → schémas, sans appel API
│   ├── test_selecteur_phase2.py      selecteur.py avec un client Mistral simulé, sans appel API
│   ├── test_confiance.py              filtrage par seuil de confiance
│   ├── test_pipeline_phase3.py         genererAffichage() : filtrage + rendu + repli sur échec
│   ├── test_registre_widgets.py         les 8 fonctions de rendu, palette, couleurs du camembert
│   ├── test_generation_outils.py         déclaration des outils + conversion des tool calls
│   └── test_pipeline_outils.py            nouveau flux bout en bout + comparaison ancien/nouveau
└── agentAffichage/
    ├── README.md              ce document
    ├── client_mistral.py       création du client (clé + garde-fou d'encodage)
    ├── pipeline.py             genererAffichage() (ancien) + genererAffichageAvecOutils() (nouveau)
    ├── rendu/                  ── partagé par les deux flux ──
    │   ├── palette.py            couleurs partagées (widgets + UI du sandbox), source unique
    │   ├── afficheur.py           afficherJoliment() : Markdown + blocs widget(s) → HTML
    │   └── registre.py             composants HTML purs (un par widget)
    ├── generation/             ── NOUVEAU flux : widgets décidés à la génération ──
    │   ├── outils.py             les 8 widgets déclarés comme outils Mistral (depuis le catalogue)
    │   ├── prompt.py              prompt système de l'agent générateur (règle de retenue)
    │   ├── generateur.py           appel unique avec tools + conversion des tool calls
    │   └── schemas.py               WidgetGenere, ToolCallInvalide, Protocol PorteurWidget
    └── selection/              ── ANCIEN flux : conservé intact pour comparaison ──
        ├── schemas.py            modèles Donnees* (réutilisés par les DEUX flux) + candidats
        ├── catalogue.py           liste déclarative des 8 widgets (réutilisée par les DEUX flux)
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
retenus) rend les rejets inspectables — c'est exactement ce que la console de
sélection (ci-dessous) expose.

Le bloc `` ```widget:type{json}``` `` (voir "Le contrat" ci-dessus) ne contient
que `donnees` — `confidence`/`raison` ne sont jamais sérialisés dans le texte
affiché, ils ne servent qu'en interne à la décision.

### Console de sélection

`genererAffichage()` renvoie un `ResultatAffichage` (`html`, `resultat_selection`,
`erreur`) au lieu d'un simple `str` — `resultat_selection` porte la liste
complète des candidats évalués (retenus ou non), `erreur` le message si l'appel
de sélection a échoué. `pipeline.py::_construire_console()` transforme ça en un
petit panneau repliable, injecté directement dans la page via le nouveau
paramètre `extra_html` de `afficherJoliment()` (celui-ci n'a pas besoin de
savoir ce que contient ce fragment, juste où l'insérer).

Résultat dans le sandbox : sous chaque message passé par la sélection (modes
"Utilisateur" et "Texte brut (Sélection + Rendu)" uniquement — "Agent (Rendu
Direct)" ne fait jamais tourner la sélection), un "▸ Console de sélection"
repliable liste chaque candidat avec son pourcentage de confiance, une barre
colorée (vert = retenu, gris = rejeté) et sa raison. En cas d'échec de la
sélection, le message d'erreur y apparaît directement.

Objectif explicite de l'utilisateur : pouvoir coller une phrase de test, voir
immédiatement pourquoi un widget a été affiché ou non, et ajuster `prompt.py`
en conséquence sans deviner.

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

### Widget `image` : une seule exception à "le texte reste compréhensible seul"

Une URL cassée (pointant vers une page web plutôt que vers le fichier image
lui-même) affiche désormais "⚠️ Image indisponible" plutôt que rien du tout
(`onerror` sur la balise `<img>`, voir `registre.image()`).

Autre correctif (18/08/2026) : une photo retenue par la sélection s'affichait
deux fois — une fois en Markdown natif (coins droits) si le texte utilisait la
syntaxe `![alt](url)`, ou en URL nue visible en texte, et une seconde fois dans
le widget (coins arrondis). `pipeline.py::_retirer_reference_image()` retire
maintenant cette référence brute (syntaxe Markdown ou URL nue) du texte source
quand — et seulement quand — le widget `image` correspondant est retenu.

C'est une **exception volontaire et isolée**, propre à `image` : les 7 autres
widgets ne touchent jamais au texte source (voir "Le contrat" plus haut — le
Markdown doit rester compréhensible sans les widgets). Une photo est le seul
cas où le contenu dupliqué est strictement identique visuellement (l'image
elle-même), donc où le retrait ne perd aucune information.

## Les quatre modes du sandbox

`sandbox/app.py` propose quatre modes (boutons radio dans la barre latérale), qui
ne font pas tourner les mêmes étages de la pipeline :

| Mode | Ce qui tourne | Ce que le champ de saisie représente |
|---|---|---|
| **Utilisateur (API Mistral)** | conversation → sélection → rendu (ANCIEN) | une question posée à Mistral |
| **Génération + Outils UI (nouveau)** | appel unique avec outils → rendu (NOUVEAU) | une question posée à Mistral |
| **Texte brut (Sélection + Rendu)** | sélection → rendu (pas de conversation) | le texte brut tel qu'il sortirait déjà de Mistral — on se branche directement à l'entrée de la pipeline |
| **Agent (Rendu Direct)** | rendu seul | la réponse déjà formatée, avec un bloc `` ```widget:type{json}``` `` écrit à la main si besoin |

**Comparer les deux architectures** : les modes *"Utilisateur (API Mistral)"* et
*"Génération + Outils UI"* prennent tous deux une **question** en entrée — posez
la même dans les deux et comparez le résultat. La console en bas de chaque
message indique lequel des deux a tourné ("Console de sélection" pour l'ancien,
"Console de génération" pour le nouveau) et ce qui a été décidé.

Le mode **"Texte brut (Sélection + Rendu)"** reste le plus utile pour tester
l'ancienne sélection sur des cas construits à la main, sans dépendre de ce que
le vrai Mistral est capable de répondre.

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

Pendant pour le nouveau flux (`generer_avec_outils()`), qui affiche le Markdown
produit, les outils appelés et les éventuels tool calls refusés :

```bash
PYTHONUTF8=1 .venv/bin/python3 verifier_generation.py
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
- [x] **Console de sélection + correctif photo (18/08/2026)** — `genererAffichage()` renvoie maintenant `ResultatAffichage` (`html`, `resultat_selection`, `erreur`) ; panneau "Console de sélection" injecté dans chaque message (modes Utilisateur / Texte brut), listant tous les candidats avec confidence, statut et raison. Widget `image` : la référence brute (Markdown ou URL nue) est retirée du texte source quand le widget est retenu, exception isolée à ce seul widget — corrige l'affichage en double de la photo.
- [x] **Nouvelle architecture (20/08/2026, branche `new_architecture`)** — widgets décidés à la génération via le tool calling de Mistral (`generation/`), en parallèle de l'ancien flux conservé intact. 4ᵉ mode dans le sandbox pour comparer les deux sur la même question. Voir "Nouvelle architecture" en haut de ce document.
- [x] **124/124 tests passent** (63 existants + 29 sur la nouvelle architecture + 11 de non-régression sur les bugs du 20/08 + 5 sur les métriques + 16 sur les bugs du 21/08).
- [x] **Métriques temps + tokens (21/08/2026)** — nouveau `metriques.py` (`Metriques`, partagé) : temps d'appel Mistral, temps de traitement local, tokens (prompt/completion/total) quand l'API les fournit — vérifié dans le SDK, préservé aussi bien par `client.chat.parse()` que `client.chat.complete()`. Affiché en tête de chaque console ("⏱ ... ms · 🔤 ... tokens"). `selectionner_widget()` renvoie maintenant `AppelSelection(resultat, metriques)` — `ResultatSelection` lui-même n'a pas bougé, c'est le schéma envoyé à Mistral, lui ajouter des champs annexes changerait ce qu'on lui demande de produire.
- [x] **Bugs corrigés le 20/08/2026** (voir `bugs_new_architecture.txt` et `tests/test_bugs_new_architecture.py`) :
  - **Nombres refusés** — Pydantic v2 convertit `"430"` en float mais refuse `1957` en `str`. Un modèle qui remplit un widget envoie pourtant naturellement des nombres (`{"date": 1957}`, une population à `1425000000`) : quatre widgets sur huit rejetaient donc des appels parfaitement légitimes. Corrigé par `TexteSouple` dans `selection/schemas.py`, qui convertit les nombres en texte à la validation.
  - **Graphiques écrasés** — le canvas se réduisait à ~190×95 px au lieu de la pleine largeur. Cause : Chart.js exige en mode responsive que le parent du canvas lui soit **dédié**, or le nôtre contenait aussi le titre. Corrigé par un conteneur dédié de hauteur fixe + `maintainAspectRatio: false` (mesuré : 1185×280 px après correctif).
  - **Code affiché deux fois** — le modèle écrivait le code dans son Markdown *et* appelait l'outil. `pipeline._retirer_bloc_code()` retire le bloc Markdown quand son contenu correspond à celui du widget, même principe que pour l'image.
  - **Console sans données** — la console de génération n'affichait que le type du widget appelé, rendant indiagnosticable un widget mal rempli (URL d'image erronée). Elle montre désormais le JSON envoyé par le modèle.
  - **Tableau jamais déclenché** — seuil trop vague dans le catalogue ; remplacé par un critère chiffré (au moins 4 lignes et 3 colonnes) avec un exemple positif explicite.
- [x] **Bugs corrigés le 24/08/2026** (relevés en test manuel sur les questions 1-10 de `bugs_new_architecture.txt`) :
  - **Deux appels au même outil dans une réponse** — le modèle a appelé deux fois `afficher_chart`, une fois avec des données complètes et une fois tronquées, produisant deux graphiques dont un faux. Corrigé à deux niveaux : le prompt l'interdit explicitement, et `convertir_tool_calls()` ne retient qu'un appel par type d'outil. L'ordre compte — les appels sont **validés avant** d'être dédupliqués, donc un premier appel malformé laisse sa place au suivant au lieu de faire perdre le widget. Les doublons écartés apparaissent dans la console de génération.
  - **Graphiques aux catégories manquantes ou décalées** — `categories: []` alors que 9 valeurs étaient fournies (constaté deux fois). Le renderer associe positionnellement `categories[i]` à `valeurs[i]` : sans étiquettes, l'axe est muet. `DonneesChart` impose désormais des catégories non vides et de même longueur que les valeurs de **chaque** série (`model_validator`), avec un message d'erreur lisible dans la console. `minItems` figure aussi dans le schéma JSON envoyé au modèle, ce qui décourage le problème en amont.
  - **`unite` remplie avec un paragraphe entier** de contexte et de sources. Champ accessoire : rejeter tout le graphique serait disproportionné, la valeur aberrante est donc simplement abandonnée (`_unite_courte`) et le graphique reste affichable. `maxLength` + description explicite dans le schéma.
  - **Sous-déclenchement de `code` et `table`** — la règle de retenue seule ("les faux positifs sont pires que les faux négatifs") poussait le modèle à ne rien appeler même sur des cas francs (fonction Fibonacci, requête SQL, comparaison 5×4). Le prompt indique maintenant que **ne pas appeler est une erreur au même titre qu'un appel abusif** quand le cas correspond clairement, avec des exemples positifs concrets. Le catalogue définit "substantiel" par un critère vérifiable (≥ 2 lignes, ensemble autonome) et nomme explicitement la requête SQL.
  - **`card` utilisée pour comparer plusieurs entités** (démographie France/Allemagne/Italie). Une card décrit UNE entité : le catalogue porte désormais un contre-exemple explicite qui renvoie vers le tableau ou le graphique.
  - **Réponses trop longues** — aucune consigne de concision n'existait dans `generation/prompt.py`, qui ne portait que des règles de sélection de widget. Ajoutée, séparée de ces règles.
  - **Code encore dupliqué malgré le correctif du 20/08** — `_retirer_bloc_code()` ne comparait qu'à l'identique (espaces ignorés) : un commentaire ajouté ou des espaces autour des opérateurs suffisaient à laisser passer le doublon. Seconde passe ajoutée par similarité (`SequenceMatcher`, seuil 0.85, seulement sur le bloc le plus proche). Seuil choisi sur mesure réelle : une reformulation légère du même code donne ~0.93, deux fonctions différentes de forme voisine plafonnent vers 0.65-0.69.
  - **Photo inventée** — non corrigé, volontairement : décidé le 24/08/2026 qu'un vrai tool de recherche d'image sera ajouté dans l'architecture réelle. Mistral n'a aucune capacité de recherche d'image, aucun correctif de prompt ne peut y suppléer.
- [x] **Saisie multi-ligne dans le sandbox (24/08/2026)** — `sandbox/app.py` : le `QLineEdit` de la barre de prompt devient `ChampSaisieWidget` (QTextEdit). Entrée envoie, **Maj+Entrée** passe à la ligne, le collage multi-ligne conserve ses retours. La hauteur suit le contenu jusqu'à 8 lignes puis le champ défile. Coller depuis une page web n'amène pas sa mise en forme (`setAcceptRichText(False)`).
- [ ] **À vérifier avec un vrai appel Mistral** — le nouveau flux n'a été testé qu'avec un client simulé. Deux points spécifiquement à observer : le palier de modèle nécessaire pour un tool calling fiable, et le comportement de `strict: true` sur les schémas de fonction (constante `SCHEMA_STRICT` dans `generation/outils.py`, facile à désactiver si l'API la refuse — notre validation Pydantic reste la vraie garantie). Lancer `verifier_generation.py`.
- [ ] **Décision à prendre avec Antoine** — la séparation "l'agent conversationnel ignore les widgets" était sa consigne initiale ; le nouveau flux s'en écarte délibérément. À valider avant de retirer `selection/`.
- [ ] **Phase 5** — robustesse (grille de test manuelle) sur le nouveau catalogue
- [ ] **Phase 6** — bilan avec Antoine

