# Reprise dans Codex Cloud

État de référence : 24 octobre 2026. Les fichiers de configuration et les dernières demandes de l’utilisateur font autorité si ce document devient ancien.

## Projet

- Dépôt : `ThomasRoehm/actu`, branche de production `main`.
- Application : https://thomasroehm.github.io/actu/
- Le site est hébergé sur GitHub Pages. Codex Cloud sert à développer, pas à héberger le site ni à remplacer la collecte.
- Le dépôt, l’application et la sélection de mangas sont publics. L’utilisateur a décidé de les laisser ainsi pour l’instant, sans changer son pseudonyme GitHub.
- Aucun compte Cloudflare ni planificateur externe n’a été configuré pour ce projet.

## État fonctionnel

- 24 sources d’actualités configurées dans `sources.json` et 29 séries dans `mangas.json`.
- Catégories Tout / Tech / Sport / Local / BD, puis `/` et Fr / Us.
- Tech, Sport et Local : articles des dernières 48 heures.
- Bouletcorp : dernière publication conservée quelle que soit sa date.
- MangaKatana : dernier chapitre disponible de chaque série, avec date si connue ; les mangas restent visibles dans BD avec Fr comme Us.
- Local suit Actu.fr Grand Bourgtheroulde et, sur demande de l’utilisateur, Le Monde · En continu via son flux RSS officiel, tous deux en français avec une rétention de 48 heures. Une catégorie vide est normale lorsqu’aucun article ne date des dernières 48 heures.
- Apple Newsroom est en Tech / Fr ; Microsoft Blog, Macworld, TechCrunch et Digital Minimalist sont en Tech / Us. NFL et NBA sont en Sport / Us.
- BeBasket, The Verge et Maliki ont été retirés sur demande : ne pas les réintroduire. Du code et des icônes historiques peuvent subsister sans être utilisés.

## Dernières décisions d’interface

- Page sans titre introductif ni champ de recherche.
- Logo : trois lignes blanches arrondies et un point bleu sur fond sombre, dans `icon.svg`.
- Aucun bouton pour rafraîchir ou synchroniser : l’ancien bouton créait une confusion avec le déclenchement d’une collecte.
- Aucun compteur de résultats sous le menu.
- À côté de Sources, une icône d’actualisation suivie de l’âge de la collecte, purement informative.
- Sur petit écran, le bloc Sources / indicateur peut passer à la ligne pour conserver la lisibilité des filtres.
- Chaque article s’ouvre sur son site d’origine ; aucun contenu complet n’est stocké.

## Automatisation actuelle

- GitHub Actions : déclenchement prévu toutes les 5 minutes, plus chaque push sur `main` et déclenchement manuel via GitHub.
- Les retards du planificateur GitHub sont connus ; une cadence garantie n’a pas été mise en place.
- Les scripts testent les données, collectent, fusionnent les résultats persistants, puis publient le site.
- Les mangas sont revérifiés au plus une fois toutes les 30 minutes par série, même si le workflow est lancé plus souvent.
- Les deux fichiers JSON de données sont commités par le bot GitHub. Prévoir ces mises à jour concurrentes lors de l’intégration des changements.

## Environnement de travail conseillé

- Python 3.12 correspond à la CI ; le code vise Python 3.9 ou supérieur.
- Pas de `pip install` ni de `npm install` nécessaire pour le projet.
- Node peut servir à `node --check app.js`. Un navigateur peut servir aux vérifications visuelles.
- Vérification initiale sans réseau : `python3 -m unittest discover -s tests -v` (15 tests à la date de cette reprise).
- Pour des tests de collecte réelle, autoriser uniquement les destinations nécessaires aux sources et leurs redirections légitimes. Ne pas ajouter de secrets au dépôt pour obtenir l’accès réseau.
- Les tests visuels ponctuels utilisés sur le Mac précédent ne font pas partie du dépôt ; ne pas dépendre de chemins `/Users/...` ni d’un profil de navigateur local existant.

## Première tâche suggérée

Lire `AGENTS.md`, `README.md` et ce document. Vérifier l’état du dépôt et exécuter les tests hors réseau. Résumer l’architecture et signaler les éventuels obstacles de l’environnement cloud, sans changer le comportement ni publier de modification tant qu’une nouvelle demande n’a pas été donnée.

Le fil de conversation précédent n’est pas nécessaire pour travailler sur le code ; ces fichiers résument les choix utiles. Ils ne remplacent pas les futures instructions de l’utilisateur.
