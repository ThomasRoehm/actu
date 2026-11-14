# Audit du 12 novembre 2026

Audit ciblé de l’interface avec Modern Web Guidance, sans changement de sources, de collecte ni d’hébergement.

## Résultats et corrections

| Point | Avant | Après |
| --- | --- | --- |
| Polices de secours, fichiers complets normal + gras | TTF, 677 408 octets | WOFF2, 291 540 octets (−57 %) |
| Contraste des onglets inactifs, mode clair | 4,34:1, inférieur à 4,5:1 | 4,83:1, vérifié par axe-core |
| Agrandissement du texte | Tailles fixées en pixels | Tailles en rem, racine laissée au navigateur |
| Texte à 200 %, largeur 320 px | Navigation susceptible de déborder | Navigation et menu Sources passent à la ligne |

La conversion WOFF2 conserve les caractères et les tables de la police ; la licence DejaVu reste dans `fonts/LICENSE.txt`. SF Mono reste prioritaire si disponible localement. Aucun fichier Apple n’est distribué.

Les polices de secours utilisent `font-display: optional` pour éviter un changement tardif sur connexion lente : la police système peut rester affichée lors de la première visite. Le navigateur peut utiliser la police téléchargée lors d’une visite suivante. Aucun préchargement forcé ne fait télécharger DejaVu aux appareils disposant déjà de SF Mono.

`font-size-adjust: from-font` améliore la cohérence des polices lorsqu’il est pris en charge. Le navigateur ignore la propriété sinon. L’option native `text-scale` est une amélioration progressive ; les navigateurs qui l’ignorent conservent le zoom habituel. Les titres restent à 12 px avec les réglages de texte par défaut.

## Vérifications effectuées

- axe-core : aucune violation automatique des règles WCAG A/AA sélectionnées sur le fil et le dialogue Sources, en clair et sombre (les vérifications manuelles restantes ne constituent pas une certification).
- Chromium automatisé : 320, 390 et 1280 px, clair/sombre, filtres BD/Sport/Tech, fermeture du dialogue par Échap et retour du focus, rendu préservé après erreurs réseau et données invalides.
- Texte doublé : titres à 24 px, sans débordement horizontal du document ni du dialogue à 320 px.
- Les 24 tests Python existants, la syntaxe JavaScript et `git diff --check` passent.
- Les caractères des polices originales et converties ont été comparés.

## Limites

Les vérifications utilisent des données locales déterministes. La réduction mesurée porte sur les octets des fichiers de police ; elle n’est pas une mesure du temps de chargement sur un appareil réel. Aucun gain LCP/INP/CLS chiffré n’est revendiqué.

WebKit a finalement pu démarrer avec des bibliothèques Debian officielles extraites dans `/tmp`, sans installation système ni dépendance ajoutée au site. Il s’agit du moteur automatisé Playwright WebKit sur Linux, pas d’un appareil Apple réel. Le rendu SF Mono sur macOS, Dynamic Type, VoiceOver et les barres système d’iOS restent à vérifier sur appareil.

## Complément WebKit

Problèmes reproduits puis corrigés :

- Boutons tactiles de 36–40 px : taille minimale portée à 44 × 44 px pour les pointeurs tactiles ; les lignes d’articles restent compactes.
- Bouton de fermeture du dialogue Sources hors écran après défilement en paysage : en-tête rendu collant dans le dialogue.
- Sélection commencée dans le dialogue puis relâchée sur le fond : l’ancien gestionnaire fermait le dialogue. Utilisation de `closedby="any"` quand il est pris en charge ; repli pointerdown/pointerup/pointercancel exigeant un début et une fin hors du dialogue.
- Marges de sécurité complétées en haut et en bas avec `safe-area-inset-top/bottom`. Leur effet avec une encoche réelle reste à contrôler sur appareil.

Contrôles réalisés dans WebKit et Chromium :

- Filtres, données inchangées, erreurs réseau et données invalides, zoom de texte à 200 %, thèmes clair/sombre, largeurs 320/390/1280 px.
- WebKit tactile : 320 × 568, 390 × 844, 844 × 390, 820 × 1180 et 1180 × 820 ; aucun débordement horizontal et fermeture visible à la fin de la liste Sources.
- Fermeture par bouton, fond et Échap ; pas de fermeture sur les marges internes ni après une sélection glissée vers le fond ; focus contenu dans le dialogue et retour au bouton Sources.
- Même parcours avec prise en charge de `closedby` désactivée pour exercer le repli ancien Safari. Ce test ne remplace pas l’exécution sur une ancienne version de Safari.
- 24 tests Python, syntaxe JavaScript et vérification des différences passent.

Le confinement du défilement de fond reste une amélioration progressive : les anciens WebKit ne respectent pas toujours `overscroll-behavior` sur un fond non défilant. Aucun verrouillage du défilement racine n’est appliqué ; la modalité et le confinement du focus restent natifs.


## Fiabilité de l’actualisation

- L’échec du chargement des actualités est conservé dans l’état et reste affiché si le chargement des mangas réussit, si un filtre change ou si le rendu périodique se déclenche. Seul un chargement valide des actualités efface cette erreur.
- Les erreurs mangas restent indépendantes ; les derniers chapitres connus restent accessibles.
- Les lignes inchangées sont réutilisées. Une mise à jour conserve la position de la première ligne visible encore présente et restaure son focus clavier si nécessaire. Si une ligne disparaît, une voisine visible sert de repère ; en haut de page, les nouveautés restent immédiatement visibles. Aucun suivi de lecture n’est enregistré.
- Tests de régression Chromium et WebKit : erreurs partielles et rétablissement, insertion au-dessus de la lecture, suppression d’une ligne visible, focus clavier, haut de page et mangas conservés après échec.
- Test reproductible : `node tests/refresh.test.cjs`, avec Playwright installé dans l’environnement de développement et ses navigateurs disponibles. Les variables optionnelles `ACTU_CHROMIUM_EXECUTABLE` et `ACTU_WEBKIT_EXECUTABLE` permettent d’utiliser des exécutables existants. Aucun de ces outils n’est chargé par le site. Les réponses réseau sont des fixtures locales.


## Recalculs des longues listes

Les tris, conversions de dates, répartitions par onglet et compteurs sont maintenant partagés dans une vue dérivée en mémoire. Elle est invalidée aux changements de données, à la prochaine publication future, à l’expiration exacte d’un article ou au prochain minuit local. Un recul de l’horloge force également le recalcul. Aucun cache persistant n’est ajouté.

Mesure indicative sur une liste synthétique de 1 000 articles, 30 appels de rendu consécutifs d’une vue inchangée, même environnement de test :

| Moteur | Médiane avant | Médiane après |
| --- | --- | --- |
| Chromium | 3,4 ms | 0,2 ms |
| WebKit | 35 ms | Inférieure à la résolution d’environ 1 ms du test |

Il s’agit du travail JavaScript d’une vue déjà chargée, pas d’une mesure LCP/INP, du réseau, du premier affichage ou d’un appareil Apple réel.

Les tests de régression couvrent aussi le remplacement simultané d’un article expiré par une publication future (nombre total inchangé), les compteurs par source dans Sources et le passage à minuit sans nouvelle réponse réseau.


## Onglet Scores

- NBA/NFL : classements ESPN de la saison indiquée par la source, par conférence ; résultats uniquement si le statut est terminé et les deux scores sont explicites. NFL consultée par semaines pour éviter les journées sans match.
- Élite 2 : classement et derniers matchs fournis par la page publique LNB, saison lue depuis la configuration annoncée par le site.
- Les sous-sections classement/résultats conservent séparément leurs données en cas d’échec ; aucun score ni résultat n’est inventé pour combler une panne.
- Collecte réelle initiale validée : 30 équipes NBA, 32 NFL, 20 Élite 2, avec respectivement 20, 20 et 10 derniers matchs terminés disponibles lors du contrôle. Les nombres peuvent évoluer.
- Chromium et WebKit : trois ligues, clair/sombre, 320/390/1280 px, zoom à 200 %, retour aux articles, Sources, récupération après erreur réseau, conservation des données après échec partiel. Aucun appel tiers depuis le navigateur ; les données sont servies par le même site.
- axe-core : aucune violation automatique des règles WCAG A/AA sélectionnées sur l’écran contrôlé. Les tableaux utilisent caption, en-têtes de colonnes et de lignes, et un conteneur défilant nommé accessible au clavier.
- Tests de collecteur indépendants du réseau dans `tests/test_scores.py`, tests navigateur optionnels avec fixtures dans `tests/scores.test.cjs` (mêmes prérequis Playwright que `tests/refresh.test.cjs`).
- Workflow : collecte sports ajoutée, Node 22 et Chrome requis côté runner, `data/scores.json` conservé entre collectes, `scores.js` inclus dans les fichiers publiés. Aucun déploiement n’est effectué pour vérifier une branche.
