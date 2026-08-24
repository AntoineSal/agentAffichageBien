# HANDOFF — Passation de session Claude Code

Document généré le 21/08/2026, en fin de session, parce que la fenêtre de
contexte de la session en cours arrive à saturation. Rédigé en inspectant
l'état réel du dépôt (git, fichiers, tests exécutés) — pas seulement la
conversation qui l'a précédé. Tout ce qui suit a été vérifié, pas supposé.

---

## 1. Contexte du projet

**Ce que fait le projet** : `agentAffichageBien` est le dépôt de travail d'un
stage chez EchoSocial (messagerie avec marketplace d'agents IA). Une
application desktop PySide6 (`main.py` + `sandbox/`) sert de bac à sable pour
développer et tester, hors du vrai backend, une fonction `afficherJoliment()`
qui transforme du texte en HTML affiché dans un moteur Chromium isolé
(`QWebEngineView`).

**Objectif de la partie sur laquelle on travaille** : le stagiaire est
responsable de l'**affichage** (comment enrichir visuellement une réponse
d'agent conversationnel avec des widgets — graphique, tableau, fiche...), pas
de la **sélection des capacités/tools** de l'agent (ça, c'est déjà géré côté
équipe réelle dans `reseau_social/jarvis/`, hors de ce dépôt). Cette frontière
a été posée explicitement tôt dans le stage et n'a jamais été remise en cause.

**Problème initial qui a motivé le système de widgets** : un agent
conversationnel (Mistral) répond en Markdown brut. Certaines réponses
(séries de nombres, comparaisons, chronologies...) gagneraient à être
affichées autrement qu'en texte — mais il fallait un mécanisme fiable pour
décider *quand* un widget apporte vraiment quelque chose (pas systématiquement
— une règle de retenue conservatrice est au cœur du projet depuis le début) et
*comment* le représenter de façon à ce que le rendu final reste robuste même
si la donnée est incomplète ou invalide.

---

## 2. Architecture actuelle (deux flux, coexistants)

Le dépôt contient **deux pipelines complets, tous les deux fonctionnels**,
qu'on peut comparer sur les mêmes questions dans le sandbox :

```
ANCIEN   Utilisateur → Mistral #1 (conversation, texte libre)
                     → Mistral #2 (sélection dédiée, sortie structurée)
                     → filtre déterministe par score de confiance
                     → annotation du texte (blocs ```widget:type{json}```)
                     → rendu (Markdown + widgets → HTML)
                     → affichage (QWebEngineView)

NOUVEAU  Utilisateur → Mistral unique (répond ET appelle des outils d'affichage)
                     → séparation content (Markdown) / tool_calls (widgets)
                     → conversion + validation des tool calls
                     → annotation du texte (même contrat de blocs)
                     → rendu (INCHANGÉ, partagé avec l'ancien flux)
                     → affichage (QWebEngineView)
```

Point d'entrée unique des deux : `agentAffichage/pipeline.py`, avec deux
fonctions publiques :
- `genererAffichage(texte_brut, fichiers=None, api_key=None) -> ResultatAffichage` — ANCIEN flux
- `genererAffichageAvecOutils(message_utilisateur, fichiers=None, api_key=None) -> ResultatAffichage` — NOUVEAU flux

Les deux renvoient le même type `ResultatAffichage` (NamedTuple) :
`html: str`, `resultat_selection: Optional[ResultatSelection]` (ancien flux
seulement), `resultat_generation: Optional[ResultatGeneration]` (nouveau flux
seulement), `erreur: Optional[str]`.

**Composants et responsabilités :**

| Dossier | Rôle | Utilisé par |
|---|---|---|
| `agentAffichage/selection/` | ANCIEN flux : sélection dédiée, sortie structurée, score de confiance | `genererAffichage()` uniquement |
| `agentAffichage/generation/` | NOUVEAU flux : appel unique avec tool calling | `genererAffichageAvecOutils()` uniquement |
| `agentAffichage/rendu/` | Rendu HTML, **partagé, identique pour les deux flux** | les deux |
| `agentAffichage/pipeline.py` | Orchestrateur des deux flux + consoles de debug | point d'entrée du sandbox |
| `agentAffichage/metriques.py` | Temps d'appel/traitement + tokens, partagé | les deux |
| `agentAffichage/client_mistral.py` | Création du client Mistral (clé + garde-fou encodage) | NOUVEAU flux uniquement (voir §4) |
| `sandbox/` | Application PySide6, 4 modes pour tester/comparer | interface utilisateur du stagiaire |

---

## 3. Widgets

Catalogue fermé à **8 widgets génériques** (pas de widget par domaine — ex.
météo/calendrier — tout se représente via un de ces 8 types structurels).
Déclaré une seule fois dans `agentAffichage/selection/catalogue.py`
(`CATALOGUE`), **réutilisé par les deux flux** (l'ancien pour générer son
prompt, le nouveau pour générer ses déclarations d'outils).

| Widget (clé) | Rôle | Modèle de données (`selection/schemas.py`) | Renderer (`rendu/registre.py`) |
|---|---|---|---|
| `image` | Affiche une image déjà référencée par une URL utilisable | `DonneesImage(url, alt?, legende?, source?)` | `image()` |
| `table` | Tableau interactif (tri/filtre/recherche implicites côté rendu HTML natif) | `DonneesTable(titre?, colonnes, lignes)` | `tableau()` |
| `code` | Bloc de code avec coloration syntaxique (highlight.js, CDN) | `DonneesCode(code, langage?, titre?)` | `code()` |
| `file` | Fichier téléchargeable référencé | `DonneesFichier(url, nom?, type_fichier?, taille?)` | `fichier()` |
| `card` | Entité avec plusieurs attributs (personne, entreprise, produit...) | `DonneesCard(titre, sous_titre?, attributs: [AttributCard])` | `carte()` |
| `chart` | Graphique (Chart.js, CDN) — ligne/barres/secteurs/nuage_points | `DonneesChart(titre?, type_graphique, categories, series: [SerieChart], unite?)` | `graphique()` |
| `stats` | Quelques indicateurs numériques clés | `DonneesStats(titre?, indicateurs: [Indicateur])` | `statistiques()` |
| `timeline` | Séquence chronologique d'événements | `DonneesTimeline(titre?, evenements: [EvenementTimeline])` | `chronologie()` |

**Format attendu** : le rendu consomme un bloc texte
`` ```widget:<cle>\n{json}\n``` `` (regex `_WIDGET_BLOCK_RE` dans
`rendu/afficheur.py`). Ce contrat est **identique pour les deux flux** — voir
§7.

**Convention commune à tous les widgets** : un champ absent ne produit jamais
de valeur de repli (`"?"`, `"Lieu inconnu"`) — la ligne correspondante
disparaît simplement (`_fragment()`/`_joindre_fragments()` dans
`rendu/registre.py`).

**Widget `weather` (carte météo)** : existe toujours dans `rendu/registre.py`
(`carte_meteo()`) et dans le dispatch de `afficheur.py`, mais **retiré du
catalogue actif** — plus proposé par aucun des deux flux de sélection.
Utilisable uniquement à la main, en tapant un bloc `widget:weather` en mode
"Agent (Rendu Direct)" du sandbox.

**Limitations connues, par widget :**
- **Tous** : `TexteSouple` (dans `selection/schemas.py`) convertit un nombre
  en texte à la validation (corrige un bug réel, voir §8/§10), mais
  `DonneesChart.categories` et `SerieChart.valeurs` n'ont **aucune contrainte
  de cohérence de longueur** entre elles — un chart avec `categories: []` et
  des valeurs quand même présentes est actuellement accepté comme valide (bug
  constaté, non corrigé — voir §10).
- **`chart`** : le champ `unite` (censé être une unité courte comme "USD" ou
  "%") a été observé rempli par le modèle avec un paragraphe entier de
  contexte/sources — rien n'empêche ça dans le schéma actuel.
- **`image`** : dépend entièrement de ce que le modèle sait déjà de la
  conversation — Mistral n'a **aucune capacité de recherche d'image réelle**,
  donc sans URL déjà présente dans le texte, il en invente une plausible mais
  fausse (voir §8/§10).
- **`code`** : le retrait du bloc Markdown dupliqué (`_retirer_bloc_code()`
  dans `pipeline.py`) ne fonctionne que si le code du bloc correspond
  **exactement** (après normalisation des espaces) à celui envoyé à l'outil —
  si le modèle reformule légèrement entre les deux, la duplication n'est pas
  retirée (bug constaté, non corrigé — voir §10).

---

## 4. Architecture de sélection (ANCIEN flux — conservé intact)

**Où** : `agentAffichage/selection/` (`selecteur.py`, `schemas.py`,
`catalogue.py`, `prompt.py`, `confiance.py`).

**Comment ça fonctionne** : un appel Mistral **séparé** de la conversation,
qui ne voit **que** le texte déjà écrit par l'agent (pas la question
d'origine, pas le contexte de conversation), et décide après coup si un
widget doit l'accompagner.

**Appel Mistral utilisé** (`selecteur.py::selectionner_widget()`) :
```python
client = Mistral(api_key=cle)
reponse = client.chat.parse(
    model="mistral-large-latest",
    messages=[
        {"role": "system", "content": construire_prompt_selection()},
        {"role": "user", "content": texte_brut},
    ],
    response_format=ResultatSelection,
)
resultat = reponse.choices[0].message.parsed
```

**Structured output** : `response_format=ResultatSelection` — Custom
Structured Outputs du SDK `mistralai` (`client.chat.parse`), qui contraint
**toute la réponse** au schéma Pydantic `ResultatSelection`
(`candidats: List[WidgetCandidat]`, union discriminée sur `type`, max 5).

**Confidence score** : chaque candidat (`WidgetImage`, `WidgetTable`, etc.)
porte `confidence: float` (0–1) et `raison: str`, calculés par le modèle
lui-même selon 5 dimensions pondérées décrites dans
`selection/prompt.py::_CONFIANCE` (pertinence 25%, complétude 20%, **valeur
ajoutée 35%**, clarté 10%, redondance 10%). Le modèle **ne filtre jamais
lui-même** — il rapporte honnêtement tous les candidats, même faibles.

**Seuil** : `selection/confiance.py::SEUIL_AFFICHAGE = 0.75`. Filtrage
déterministe, en Python pur, séparé du modèle :
`widgets_retenus(resultat) -> [c for c in resultat.candidats if c.confidence >= SEUIL_AFFICHAGE]`.

**Fichiers concernés :**
- `selection/schemas.py` — modèles `Donnees*` (réutilisés aussi par le
  nouveau flux, voir §5) + enveloppe `WidgetCandidat`/`ResultatSelection`
  avec `confidence`/`raison` (propres à ce flux).
- `selection/catalogue.py` — `CATALOGUE` (réutilisé aussi par le nouveau
  flux).
- `selection/prompt.py` — génère le prompt système depuis `CATALOGUE`
  (règle de retenue, 5 dimensions du score, démarche en 12 étapes).
- `selection/confiance.py` — `SEUIL_AFFICHAGE` + `widgets_retenus()`.
- `selection/selecteur.py` — l'appel lui-même. Renvoie
  `AppelSelection(resultat: ResultatSelection, metriques: Metriques)`
  (NamedTuple ajouté le 21/08 pour exposer temps/tokens — voir §6).

**Ce qui a été modifié pour permettre le nouveau flux** : rien dans la
logique de `selection/`. Seuls **`schemas.py`** (ajout de `TexteSouple`,
utilisé par les deux flux car les modèles `Donnees*` sont partagés) et
**`catalogue.py`** (texte des règles `utiliser_quand`/`ne_pas_utiliser_quand`,
lu par les deux flux) ont été touchés — et seulement pour corriger des bugs
réels affectant les deux pipelines, pas pour adapter `selection/` au nouveau
flux. `selecteur.py` a gagné le renvoi des métriques (`AppelSelection` au
lieu de `ResultatSelection` nu) — un changement de signature, voir §8 pour
l'impact sur les tests.

---

## 5. Nouvelle architecture en cours (NOUVEAU flux)

```
Utilisateur → Mistral (connaît les 8 widgets via tool calling)
            → réponse avec DEUX canaux séparés dans le même message :
                 message.content     → Markdown libre, inchangé
                 message.tool_calls  → 0 à N appels d'outils d'affichage
            → conversion + validation Pydantic des tool calls
            → pipeline de rendu (INCHANGÉ)
            → HTML
```

**Pourquoi ce changement** : dans l'ancien flux, l'appel de sélection ne voit
**que** le texte final déjà écrit — jamais la question de l'utilisateur ni le
contexte de la conversation. C'est une limite structurelle : l'agent qui
génère la réponse a plus d'information que le juge qui la relit après coup.
L'idée testée ici : faire décider le widget **par l'agent qui répond
lui-même**, pendant qu'il génère, avec accès à tout le contexte.

Cette décision a été analysée en détail avant implémentation (comparaison de
4 options : bloc Markdown libre réutilisé, tags `<widget>`, sortie structurée
sur toute la réponse, function/tool calling) — **function/tool calling a été
choisi et recommandé** car c'est la seule option qui :
- garde le Markdown en texte libre, streamable (pas de schéma strict sur
  toute la réponse) ;
- donne des garanties de validation aussi fortes que la sortie structurée,
  mais **par appel d'outil**, pas sur la réponse entière — un widget invalide
  n'affecte jamais le Markdown ;
- réutilise un pattern déjà en place côté équipe réelle (tool calling déjà
  utilisé pour les vrais tools dans `reseau_social/mistral_tools/`).

**Important — ce n'est PAS une décision définitive de retirer l'ancien
flux.** Consigne explicite de l'utilisateur : garder `selection/` intact tant
que le nouveau flux n'est pas validé en conditions réelles, pour pouvoir
comparer et revenir en arrière si besoin (voir §9).

---

## 6. Mistral / tool calling — état RÉEL du code (pas une intention)

**SDK** : `mistralai` (>= 1.0, version installée : **2.9.3** — voir
`requirements.txt`). **Point d'import non standard, vérifié par
introspection** : `from mistralai.client.sdk import Mistral` — PAS
`from mistralai import Mistral` comme la documentation générale le montre
souvent. Ce détail a mordu une fois cette session ; toujours vérifier avant
de supposer un import du SDK.

**Deux modèles différents utilisés dans le dépôt, aucun changé sans raison :**
- `sandbox/utils.py::call_mistral_api()` — mode "Utilisateur" du sandbox,
  conversation simple, **`mistral-tiny-latest`**, appel `requests` brut (pas
  le SDK), aucun structured output. Non touché par ce chantier.
- `selection/selecteur.py::MODELE_SELECTION` — **`mistral-large-latest`**
  (ancien flux, sortie structurée).
- `generation/generateur.py::MODELE_GENERATION` — **`mistral-large-latest`**
  (nouveau flux, tool calling). Choisi par défaut sur le même palier que
  l'ancien flux, **pas encore ajusté empiriquement**.

**Initialisation du client** :
- Ancien flux : `Mistral(api_key=cle)` construit directement dans
  `selecteur.py`.
- Nouveau flux : `agentAffichage/client_mistral.py::creer_client(api_key)` —
  résout la clé (paramètre ou `MISTRAL_API_KEY`) et vérifie l'encodage de
  l'environnement (`locale.getpreferredencoding()` doit être UTF-8, sinon
  `RuntimeError` explicite demandant `PYTHONUTF8=1` — bug réel rencontré et
  corrigé le 17/08/2026, voir le commentaire en tête du fichier).
  **`selecteur.py` n'utilise PAS encore ce module partagé** — il a sa propre
  copie de cette logique (commentaire explicite dans `client_mistral.py` :
  "l'ancien pipeline doit rester intact tant que la nouvelle approche n'est
  pas validée"). Unification prévue seulement le jour où l'ancien flux sera
  retiré.

**Outils déjà existants dans le projet (functional tools réels)** : aucun
dans ce dépôt — les vrais tools fonctionnels (météo, etc.) sont côté backend
réel (`reseau_social/mistral_tools/`, hors de ce dépôt, lecture seule).

**Comment le tool calling fonctionne ici** (`generation/generateur.py::generer_avec_outils()`) :
```python
client = creer_client(api_key)
reponse = client.chat.complete(
    model=modele,
    messages=[
        {"role": "system", "content": construire_prompt_generation()},
        {"role": "user", "content": message_utilisateur},
    ],
    tools=construire_outils(),
    tool_choice="auto",          # "any"/"required" forceraient un widget à chaque tour
    parallel_tool_calls=True,    # autorise plusieurs widgets dans une même réponse
)
message = reponse.choices[0].message
markdown = _extraire_texte(message.content)              # gère str, liste de chunks, None
widgets, invalides = convertir_tool_calls(message.tool_calls)
```

**Ce n'est PAS une boucle de tools classique.** Un tool call n'est **jamais**
réexécuté ni renvoyé au modèle — pas de second appel. Le tool call EST le
résultat final (spécification de widget pour le renderer). Documenté en tête
de fichier de `generateur.py` et dans `agentAffichage/README.md`.

**Les outils déjà implémentés pour les widgets UI** : les 8 widgets du
catalogue, déclarés par `generation/outils.py::construire_outils()`. Chaque
outil = `{"type": "function", "function": {"name": "afficher_<cle>", "description": ..., "parameters": <json_schema>, "strict": true}}`.

- **Nom** : préfixe `afficher_` + clé du catalogue (`afficher_chart`,
  `afficher_card`...). `cle_depuis_nom_outil()` fait l'inverse et renvoie
  `None` pour tout nom inconnu — un outil inventé par le modèle ne peut donc
  jamais passer.
- **Schéma d'arguments** : généré directement depuis le modèle `Donnees*`
  correspondant via `model_json_schema()`, puis passé dans
  `rec_strict_json_schema()` pour poser `additionalProperties: false`
  récursivement. **`rec_strict_json_schema` vient d'un module PRIVÉ du SDK**
  (`mistralai.extra.utils._pydantic_helper`, préfixé `_`) — fonctionne
  aujourd'hui (vérifié, voir §8), mais c'est un import interne non garanti
  stable d'une version du SDK à l'autre. Point de vigilance pour la suite.
- **Description** : `objectif` + `UTILISER QUAND` + `NE PAS UTILISER QUAND`
  du `DescripteurWidget` correspondant dans `CATALOGUE` — donc partagée avec
  l'ancien flux, un seul endroit à modifier pour ajuster les règles des deux.
- **`strict: true`** (`outils.py::SCHEMA_STRICT = True`) : demande à l'API de
  contraindre la génération au schéma. **Pas encore vérifié avec un vrai
  appel** — si l'API le refuse, c'est une constante à passer à `False`
  facilement ; la validation Pydantic à la réception reste la vraie garantie
  quoi qu'il arrive.

**Schémas utilisés** : les modèles `Donnees*` de `selection/schemas.py`,
**réutilisés tels quels**, sans traduction — aucune structure parallèle créée
pour le nouveau flux (`generation/schemas.py` ne contient que l'enveloppe :
`WidgetGenere(type, donnees)`, `ToolCallInvalide(nom_outil, erreur,
arguments_bruts)`, `ResultatGeneration(markdown, widgets, invalides,
metriques)`, et le `Protocol PorteurWidget` qui permet à `pipeline.py` de
traiter les deux flux de façon uniforme).

**Difficultés réellement rencontrées** (vérifiées, pas supposées) :
1. `FunctionCall.arguments` est typé `Union[Dict[str, Any], str]` dans le SDK
   — l'API rend parfois le JSON déjà décodé, parfois une chaîne à parser.
   `_arguments_en_dict()` gère les deux (testé).
2. `AssistantMessage.content` est typé `Union[str, List[ContentChunk],
   None]` — `_extraire_texte()` gère les trois cas (testé).
3. Import du SDK non standard (voir plus haut).
4. **Streaming non implémenté** — voir §10, section dédiée.
5. Aucun appel Mistral réel n'a encore été fait avec ce nouveau flux dans
   cette session sans clé API disponible côté agent — voir §8.

---

## 7. Rendu — comment un widget arrive jusqu'au HTML

**C'est la partie du projet la plus stable — ne pas la réécrire.** Elle est
identique, non modifiée, pour les deux flux depuis le début de ce chantier
(seules des couleurs et deux bugs de mise en page ont été corrigés dedans,
voir §8 — jamais son architecture).

**Chaîne complète** :

1. `pipeline.py::_construire_blocs_widgets(widgets)` sérialise chaque widget
   (qu'il vienne de l'ancien ou du nouveau flux, via le `Protocol
   PorteurWidget`) en `` ```widget:<type>\n{donnees.model_dump_json()}\n``` ``.
2. `pipeline.py::_annoter_texte(texte, widgets)` retire les références
   dupliquées (image, code — voir §3/§10) puis ajoute les blocs **à la fin**
   du texte (jamais intercalés — voir §10 "position des widgets").
3. `rendu/afficheur.py::afficherJoliment(texte, fichiers, extra_html)` :
   - `_extraire_widgets()` retire les blocs `` ```widget:... ``` `` du texte
     via regex (`_WIDGET_BLOCK_RE`) AVANT le parsing Markdown, les remplace
     par des marqueurs uniques.
   - Le texte restant passe dans `markdown.markdown()` (lib `markdown`,
     extensions `extra`/`sane_lists`/`nl2br`).
   - `_injecter_widgets()` remplace les marqueurs par le HTML réel de chaque
     widget, rendu via `rendu/registre.py`.
   - `extra_html` (nouveau depuis le 21/08) : fragment optionnel injecté en
     fin de carte — c'est par ce paramètre que `pipeline.py` insère la
     console de debug, sans qu'`afficherJoliment()` ait besoin de savoir ce
     qu'elle contient.
4. `rendu/registre.py` — une fonction pure par widget (`image()`,
   `tableau()`, `code()`, `fichier()`, `carte()`, `graphique()`,
   `statistiques()`, `chronologie()`, + `carte_meteo()` pour `weather`),
   chacune prenant un `Dict` et renvoyant un fragment HTML autonome (styles
   inline, couleurs depuis `rendu/palette.py`).
5. Fallback à chaque étage : JSON invalide ou type de widget inconnu →
   `_widget_erreur()` (encart rouge + contenu brut affiché, jamais de
   crash) ; erreur de parsing Markdown → texte brut échappé.

**Structures intermédiaires** : uniquement du texte (le bloc
`` ```widget:type{json}``` ``) entre la sélection/génération et le rendu —
c'est le contrat stable qui permet aux deux flux de ne rien connaître l'un de
l'autre.

**Parsers/converters** : `_extraire_widgets`/`_injecter_widgets` dans
`afficheur.py` (texte → HTML) ; `convertir_tool_calls()` dans
`generation/generateur.py` (tool calls → `WidgetGenere`, nouveau flux
seulement — l'ancien n'a pas besoin de conversion, la sortie structurée est
déjà un objet Pydantic).

**Parties stables, à ne PAS réécrire sans raison forte** :
`rendu/afficheur.py`, `rendu/registre.py`, `rendu/palette.py`, le contrat de
bloc `` ```widget:type{json}``` ``, `pipeline.py::_construire_blocs_widgets()`.

---

## 8. État actuel

### Ce qui fonctionne (vérifié)

- **108/108 tests passent.** Commande exacte :
  ```bash
  cd "/Users/clovisjohnson/Documents/Stage Echo/agentAffichageBien"
  rm -rf agentAffichage/**/__pycache__ tests/__pycache__ .pytest_cache 2>/dev/null
  .venv/bin/python3 -m pytest tests/ -q
  ```
  Résultat au moment de ce document : `108 passed in 0.37s`.
- `sandbox.app` s'importe sans erreur (`.venv/bin/python3 -c "import sandbox.app"`).
- Les deux flux, testés avec un client Mistral **simulé** (aucun test
  automatisé de ce dépôt n'appelle jamais le vrai réseau) : réponse sans
  widget, avec un widget, avec plusieurs widgets, widget invalide qui
  n'affecte pas le Markdown, échec de l'appel qui retombe proprement.
- Rendu vérifié visuellement (navigateur, capture d'écran) le 20/08 :
  camembert avec 5 couleurs distinctes, graphique en pleine largeur
  (1185×280 px mesuré), légendes correctes.
- L'ancien flux **a été vérifié avec un vrai appel Mistral** le 17/08/2026
  (`verifier_selection.py`).

### Ce qui fonctionne partiellement / est en cours

- **Le nouveau flux (`generation/`) n'a PAS encore été vérifié avec un vrai
  appel Mistral dans cette session** — pas de clé API disponible côté agent
  (`MISTRAL_API_KEY` absente du shell de l'agent, séparé de celui de
  l'utilisateur). Tout ce qui est décrit aux §5/§6 est vérifié par
  introspection du SDK et par tests avec client simulé, **pas par un appel
  réel**. `verifier_generation.py` existe et est prêt à être lancé par
  l'utilisateur.
- **L'utilisateur A testé le nouveau flux manuellement** dans le sandbox,
  avec de vraies questions (liste de 30 questions dans
  `bugs_new_architecture.txt`, questions 1 à 10 explorées avant la rédaction
  de ce document) et a rapporté 7 comportements précis — voir "Comportements
  surprenants" ci-dessous. **Analysés en détail dans une réponse de chat,
  mais aucun correctif n'a été implémenté** sur consigne explicite de
  l'utilisateur ("ne résous pas ces problèmes").

### Ce qui est cassé (bugs connus, non corrigés)

Rapportés par l'utilisateur en testant les questions du fichier
`bugs_new_architecture.txt` en mode "Génération + Outils UI" :

1. **Photo "indisponible"** — l'URL suggérée pour tester était valide (HTTP
   200 vérifié), donc Mistral a très probablement inventé une URL plausible
   mais fausse. Cause structurelle : Mistral n'a aucune capacité de
   recherche d'image réelle.
2. **Code dupliqué** — écrit une fois en bloc Markdown brut (sans coloration,
   car `afficherJoliment` ne colore que le widget `code`, pas les blocs
   Markdown natifs) et une fois dans le widget. `_retirer_bloc_code()` ne
   matche que si le contenu est EXACTEMENT identique après normalisation des
   espaces — une reformulation du modèle entre les deux échappe au retrait.
3. **Sous-déclenchement du widget `code`** — 2 fois sur 3 sur la même
   question (fonction Fibonacci), aucun outil appelé du tout.
4. **Widget `table` jamais déclenché**, malgré l'ajustement du seuil dans
   `catalogue.py` (question "compare 5 langages de programmation").
5. **Réponse trop longue** (Marie Curie) — aucune consigne de concision dans
   `generation/prompt.py`, qui ne porte que des règles de sélection de
   widget.
6. **Deux appels au même widget `chart` sur une même réponse**, l'un
   incomplet (`categories: []` alors que 9 valeurs sont fournies, `unite`
   rempli avec un paragraphe entier au lieu d'une unité courte), l'autre
   complet. Le schéma actuel n'interdit ni les doublons d'appel au même
   outil, ni les incohérences de longueur `categories`/`valeurs`.
7. **Widget `card` mal choisi** pour comparer 3 pays (démographie
   France/Allemagne/Italie) — CARD est pensé pour UNE entité avec ses
   attributs, pas pour une comparaison entre plusieurs entités (déjà mieux
   représentée par le chart généré juste à côté sur la même question). Même
   bug de `categories: []` sur ce chart.
8. **Widget `code` jamais déclenché** sur une question SQL pourtant sans
   ambiguïté (même famille que le point 3).

Voir §10 pour l'analyse des causes et les leviers recommandés (non
implémentés).

### Derniers changements effectués (cette session, non commités)

Dans l'ordre chronologique approximatif : refonte du catalogue à 8 widgets
génériques → score de confiance (ancien flux) → palette de couleurs +
corrections visuelles → console de sélection + correctif photo doublée →
**nouvelle architecture par tool calling** (`generation/`) → correctifs de
bugs (nombres refusés, canvas écrasé, code dupliqué, console sans données,
seuil table) → **métriques temps/tokens** (dernier chantier terminé).

### Fichiers récemment modifiés (état git réel, voir §12 pour la liste complète)

Rien n'est commité depuis `7565831 Merge pull request #1 from AntoineSal/refonte_widgets`.
Tout le travail de cette session est dans l'arbre de travail (modifié ou non
suivi).

### Comportements surprenants (au-delà des bugs listés ci-dessus)

- L'import standard documenté du SDK (`from mistralai import Mistral`) ne
  fonctionne PAS avec la version installée — chemin réel :
  `from mistralai.client.sdk import Mistral` (découvert par introspection,
  pas par la doc).
- `bugs_new_architecture.txt` contenait à l'origine les 3 premiers bugs
  rapportés par l'utilisateur ; son contenu a depuis été remplacé (par
  l'utilisateur, entre deux tours de conversation) par la liste des 30
  questions de test — c'est un fichier de travail de l'utilisateur, pas un
  artefact stable du projet.

---

## 9. Décisions d'architecture (déjà prises — ne pas les remettre en cause sans raison nouvelle)

- **L'agent conversationnel ne doit jamais être modifié** dans son
  comportement de fond — contrainte du sujet de stage depuis le début. Le
  nouveau flux ne "modifie" pas l'agent, il lui ajoute des outils qu'il est
  libre d'ignorer (`tool_choice="auto"`, jamais `"required"`).
- **Pourquoi le tool calling plutôt qu'une sortie structurée sur toute la
  réponse** : préserve le Markdown en texte libre/streamable, isole les
  échecs de widget du Markdown (une sortie structurée globale est
  tout-ou-rien), et réutilise un pattern déjà utilisé côté équipe pour les
  vrais tools. Détaillé en §5.
- **Le Markdown doit rester du texte libre**, jamais transformé en JSON
  structuré dans son ensemble — c'est ce qui garantit qu'une réponse reste
  utilisable même si tous les widgets échouent.
- **Le renderer (`rendu/`) doit être conservé tel quel** — les deux flux s'y
  raccordent par le même contrat texte, sans jamais le modifier pour
  s'adapter à l'un ou l'autre.
- **Pourquoi pas de score de confiance dans le nouveau flux, pour l'instant**
  — consigne explicite : "ne rajoute pas artificiellement un confidence score
  aux UI tools sauf si tu identifies une vraie nécessité architecturale".
  Dans cette architecture, c'est le modèle générateur lui-même qui décide, il
  n'y a plus de second juge à qui demander une note. **Après avoir vu les 7
  bugs listés en §8, l'analyse fournie à l'utilisateur conclut que
  réintroduire un score n'aiderait PAS la majorité des cas observés**
  (sous-déclenchement — un score ne peut rien filtrer si l'outil n'est jamais
  appelé ; données malformées — confiance et qualité des données sont deux
  axes différents) — voir le détail des leviers recommandés à la place en
  §10/§11. **Ce n'est pas une décision figée de l'utilisateur, seulement une
  recommandation formulée** ; à rediscuter si les leviers alternatifs ne
  suffisent pas.
- **`selection/` (ancien flux) doit rester intact**, pas retiré ni
  refactoré pour "faire de la place" au nouveau — sert de comparaison et de
  filet de sécurité tant que le nouveau n'est pas validé en conditions
  réelles.
- **Le streaming n'est volontairement pas implémenté** malgré être
  structurellement possible (vérifié dans le SDK) — voir §10.

---

## 10. Problèmes / points d'attention

- **Streaming** : structurellement compatible (vérifié : `client.chat.stream()`
  existe, `DeltaMessage` porte `content` ET `tool_calls`), mais **non
  implémenté**. Deux raisons factuelles, pas de la paresse : le sandbox
  affiche chaque message d'un coup (`QWebEngineView.setHtml()`, aucun rendu
  incrémental existant à alimenter), et le comportement réel du modèle en
  streaming (fragmentation des arguments entre chunks, ordre d'arrivée,
  plusieurs tool calls en parallèle) n'a jamais été observé sur un vrai
  appel. Le champ `ToolCall.index` existe dans le SDK pour recoller des
  arguments fragmentés — pas encore exploité.
- **Tool calls multiples** : supportés (`parallel_tool_calls=True`,
  `convertir_tool_calls()` traite une liste), mais **rien n'empêche
  actuellement d'appeler deux fois le MÊME outil** dans une réponse — cause
  du bug #6 en §8.
- **Position des widgets dans la réponse** : toujours en fin de texte, jamais
  intercalés (décision explicite, documentée dans `pipeline.py::_annoter_texte()`
  et `agentAffichage/README.md`). Si un placement intercalé (texte / widget /
  texte) devient nécessaire, la voie propre identifiée est un champ d'ancrage
  optionnel (extrait verbatim du Markdown après lequel insérer), avec repli
  en fin de texte si introuvable — non implémenté, rien ne l'a démontré
  nécessaire pour l'instant.
- **Validation** : forte au niveau JSON schema (`additionalProperties:
  false` récursif) et Pydantic (types, champs requis), mais **absente au
  niveau cohérence inter-champs** — `DonneesChart.categories` peut être vide
  ou de longueur différente de `SerieChart.valeurs` sans lever d'erreur
  (bug #6/#7 en §8). Piste identifiée, non implémentée : un validateur
  Pydantic (`model_validator`) sur `DonneesChart`.
- **Erreurs de rendu** : gérées à chaque étage (JSON invalide, type inconnu,
  échec de parsing Markdown) — jamais de crash observé. Pas de point
  d'attention actif ici.
- **Fallback Markdown** : garanti dans les deux flux — un widget qui échoue
  n'affecte jamais le texte affiché. Le nouveau flux va plus loin : même un
  tool call individuellement invalide n'affecte ni le Markdown ni les autres
  widgets de la même réponse (`ToolCallInvalide`, testé).
- **Widgets trop fréquents** : **pas le problème observé actuellement** —
  c'est plutôt l'inverse (sous-déclenchement, bugs #2/#3/#4/#8 en §8). Garder
  en tête si les correctifs futurs (few-shot, etc.) faisaient sur-réagir le
  modèle dans l'autre sens.
- **Compatibilité avec les tools fonctionnels existants** : aucun tool
  fonctionnel réel n'existe dans ce dépôt (ils sont côté
  `reseau_social/mistral_tools/`, hors dépôt) — donc pas encore testé en
  pratique. Le README et ce document notent la distinction conceptuelle
  (tools UI = jamais de boucle d'exécution, tools fonctionnels = boucle
  LLM → tool → résultat → LLM) mais un scénario réel avec les deux mécanismes
  actifs simultanément sur le même appel n'a jamais été exercé.
- **Modèle Mistral** : `mistral-large-latest` utilisé par défaut pour les
  deux flux, choix non ajusté empiriquement (voir commentaires dans
  `selecteur.py`/`generateur.py`). Le support fiable du tool calling par
  palier de modèle (small/medium) n'a pas été vérifié.
- **Import privé du SDK** (`mistralai.extra.utils._pydantic_helper.rec_strict_json_schema`,
  voir §6) : fonctionne aujourd'hui, mais c'est un chemin interne non garanti
  stable entre versions du SDK.
- **`SCHEMA_STRICT = True`** (`generation/outils.py`) : pas encore vérifié
  contre un vrai appel — si l'API le refuse, facile à repasser à `False`, la
  validation Pydantic réelle n'en dépend pas.

---

## 11. Prochaines étapes

### TODO immédiats (déjà identifiés, prêts à être discutés/implémentés)

1. **Lancer `verifier_generation.py` avec une vraie clé** pour valider le
   nouveau flux en conditions réelles (jamais fait dans cette session côté
   agent, faute de clé disponible). Commande :
   ```bash
   export MISTRAL_API_KEY="votre_clé"
   PYTHONUTF8=1 .venv/bin/python3 verifier_generation.py
   ```
2. **Corriger les bugs listés en §8**, dans l'ordre de levier identifié par
   l'analyse (mais **rien n'a été validé par l'utilisateur comme plan
   d'implémentation** — à rediscuter, pas à exécuter aveuglément) :
   - Ajouter des exemples concrets d'appels d'outils réussis dans
     `generation/prompt.py` (probablement le levier le plus fort pour le
     sous-déclenchement sur `table`/`code`).
   - Interdire explicitement, dans le prompt, d'appeler deux fois le même
     outil dans une réponse.
   - Renforcer `DonneesChart` (`selection/schemas.py`) : `categories` non
     vide et de même longueur que `valeurs` ; limiter la longueur de `unite`.
   - Ajouter une consigne de concision générale dans `generation/prompt.py`,
     séparée des règles de sélection de widget.
   - Ajouter un exemple négatif explicite pour `card` dans `catalogue.py`
     ("ne pas l'utiliser pour comparer plusieurs entités entre elles").
3. **Continuer les tests manuels** sur les questions 11 à 30 de
   `bugs_new_architecture.txt` (questions 1 à 10 explorées).

### TODO importants (décidés en principe, pas encore planifiés dans le détail)

- Une fois le nouveau flux jugé fiable : discuter avec Antoine du retrait
  (ou non) de `selection/` — rappel : "l'agent ignore les widgets" était sa
  consigne initiale, le nouveau flux s'en écarte délibérément (voir §9).
- Décider si/quand implémenter le streaming, une fois le sandbox capable
  d'un rendu incrémental (actuellement `setHtml()` d'un bloc).
- Ajuster empiriquement le palier de modèle (`mistral-large-latest` vs
  small/medium) une fois le mécanisme éprouvé.

### Améliorations futures (pas encore décidées, mentionnées pour mémoire)

- Champ d'ancrage optionnel pour un placement intercalé des widgets dans le
  texte (voir §10) — non demandé, rien ne l'a démontré nécessaire.
- Unifier `client_mistral.py` et la logique dupliquée dans `selecteur.py`
  — seulement le jour où l'ancien flux est retiré.
- Phase 5 (grille de test manuelle formalisée) et Phase 6 (bilan avec
  Antoine), mentionnées dans `agentAffichage/README.md` mais pas commencées.

---

## 12. Informations importantes pour une nouvelle session

**Branche actuelle** : `new_architecture`.

**État git** : rien de commité depuis `7565831 Merge pull request #1 from
AntoineSal/refonte_widgets`. Tout le travail décrit dans ce document est dans
l'arbre de travail, non indexé.

```
Modifiés (suivis) :
  agentAffichage/README.md
  agentAffichage/pipeline.py
  agentAffichage/rendu/registre.py
  agentAffichage/selection/catalogue.py
  agentAffichage/selection/schemas.py
  agentAffichage/selection/selecteur.py
  sandbox/app.py
  tests/test_pipeline_phase3.py
  tests/test_selecteur_phase2.py
  verifier_selection.py

Non suivis (nouveaux fichiers) :
  agentAffichage/client_mistral.py
  agentAffichage/generation/  (tout le dossier : __init__.py, generateur.py, outils.py, prompt.py, schemas.py)
  agentAffichage/metriques.py
  bugs_new_architecture.txt
  tests/test_bugs_new_architecture.py
  tests/test_generation_outils.py
  tests/test_pipeline_outils.py
  verifier_generation.py
```

**Ne PAS committer sans demande explicite de l'utilisateur** — aucun commit
n'a été fait pendant toute cette session, l'utilisateur gère ses commits
lui-même.

**Fichiers importants, par ordre de priorité de lecture pour comprendre le
projet** :
1. `agentAffichage/README.md` — documentation de référence, tenue à jour à
   chaque étape, la plus complète.
2. Ce fichier (`HANDOFF.md`).
3. `agentAffichage/pipeline.py` — les deux flux, le point où tout converge.
4. `agentAffichage/generation/` — le nouveau flux en cours de fiabilisation.
5. `bugs_new_architecture.txt` — actuellement la liste des 30 questions de
   test manuel (voir §8, "comportements surprenants").

**Architecture à préserver** : voir §9 en entier. En particulier :
`rendu/` ne bouge pas, `selection/` reste intact, le Markdown reste libre,
pas de score de confiance ajouté sans nécessité démontrée.

**Décisions à ne pas annuler sans raison nouvelle** : les 8 points de §9.

**Problèmes actuellement étudiés** : les 8 bugs de §8/§10 sur le nouveau
flux — analysés, pas corrigés, en attente de validation du plan avec
l'utilisateur avant toute implémentation.

**Prochaine tâche concrète** : reprendre le test manuel du nouveau flux dans
le sandbox (questions 11 à 30 de `bugs_new_architecture.txt`), et/ou discuter
avec l'utilisateur des correctifs proposés en §11 avant de les implémenter.

**Vérifier avant de toucher au code** :
```bash
cd "/Users/clovisjohnson/Documents/Stage Echo/agentAffichageBien"
git status
.venv/bin/python3 -m pytest tests/ -q
```
Les deux doivent respectivement montrer l'état ci-dessus et `108 passed`
avant de commencer quoi que ce soit — si ce n'est pas le cas, quelque chose a
changé depuis la rédaction de ce document, ne pas supposer qu'il est encore à
jour.

---

## 13. Prompt de reprise

À copier-coller tel quel dans une nouvelle session Claude Code :

```
Cette session reprend un travail déjà en cours, documenté dans HANDOFF.md à
la racine du dépôt (/Users/clovisjohnson/Documents/Stage Echo/agentAffichageBien).
Ce fichier vient d'une session Claude Code précédente qui a atteint sa limite
de contexte — lis-le en entier avant de faire quoi que ce soit.

Avant toute modification :
1. Lis HANDOFF.md en entier.
2. Vérifie toi-même l'état réel du dépôt (git status, git branch, lancer les
   tests) plutôt que de faire confiance aveuglément à ce que HANDOFF.md
   décrit — il peut avoir légèrement vieilli. Commande de vérification :
   cd "/Users/clovisjohnson/Documents/Stage Echo/agentAffichageBien" && git status && .venv/bin/python3 -m pytest tests/ -q
3. Lis aussi agentAffichage/README.md, qui est la documentation de référence
   tenue à jour du projet.

Contraintes importantes à respecter, déjà décidées (détail en §9 de
HANDOFF.md) — ne les remets pas en question sans raison nouvelle et sérieuse :
- Le dépôt contient DEUX pipelines de widgets qui coexistent volontairement :
  l'ancien (agentAffichage/selection/, sélection dédiée après coup) et le
  nouveau (agentAffichage/generation/, tool calling pendant la génération).
  Les deux fonctionnent, les 108 tests actuels passent pour les deux. Ne
  supprime ni ne fusionne rien entre les deux sans qu'on te le demande
  explicitement.
- Le rendu (agentAffichage/rendu/ : afficheur.py, registre.py, palette.py)
  est stable et partagé par les deux flux — ne le réécris pas.
- Le Markdown de la réponse doit toujours rester du texte libre, jamais
  transformé en JSON structuré dans son ensemble.
- N'ajoute pas de score de confiance au nouveau flux sans nécessité
  démontrée — consigne explicite de l'utilisateur, déjà expliquée pourquoi
  en §9 de HANDOFF.md.
- Ne commit jamais sans demande explicite.

Prochaine tâche : le nouveau flux (tool calling) a été testé manuellement par
l'utilisateur dans le sandbox sur les 10 premières questions de
bugs_new_architecture.txt, qui a révélé 8 bugs/comportements précis
(sous-déclenchement de widgets, doublons d'appel au même outil, données de
graphique incohérentes, mauvais choix de widget, réponses trop longues —
détail complet en §8 et §10 de HANDOFF.md). Une analyse des causes et des
correctifs possibles a déjà été donnée à l'utilisateur en chat (résumée en
§11 de HANDOFF.md) mais RIEN n'a été implémenté — l'utilisateur avait
explicitement demandé de ne rien corriger avant d'avoir cette passation.

Commence par demander à l'utilisateur s'il veut : (a) continuer les tests
manuels sur les questions 11-30, (b) discuter/valider les correctifs proposés
en §11 avant implémentation, ou (c) autre chose. Ne commence pas à corriger
les bugs de ta propre initiative sans confirmation — ce sont des changements
de prompt et de schéma qui affectent le comportement du modèle, pas de la
simple correction de bug mécanique.
```
