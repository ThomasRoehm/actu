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

WebKit a été téléchargé mais ne peut pas démarrer dans cet environnement : bibliothèques GTK4, Graphene, HarfBuzz ICU, Manette, Hyphen et GLES absentes. Le rendu sur Safari réel, Dynamic Type sur iPhone/iPad et VoiceOver restent à vérifier sur appareil Apple. L’audit automatisé ne remplace pas ces contrôles.
