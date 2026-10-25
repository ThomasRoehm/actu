# Consignes pour travailler sur Actu

## Communication et périmètre

- Répondre en français, simplement et brièvement. L’utilisateur n’est pas développeur.
- Lire `README.md` et `HANDOFF.md` avant une première intervention.
- Faire des changements ciblés, sans refonte, changement d’hébergement ou ajout de dépendances non demandé.
- Ne pas changer la visibilité du dépôt, le nom du compte, les sources ou les règles de conservation sans demande explicite.

## Architecture

- Site statique HTML/CSS/JavaScript sans framework ni étape de compilation.
- `index.html`, `style.css`, `app.js` : interface et rechargement des données publiées.
- `sources.json` : sources d’actualités ; `mangas.json` : sélection MangaKatana.
- `scripts/collect.py` et `scripts/mangas.py` : collecte Python standard, sans paquet externe.
- `data/articles.json` et `data/mangas.json` : données persistantes, mises à jour par GitHub Actions.
- `.github/workflows/publish.yml` : tests, collecte, conservation des données, déploiement GitHub Pages.

## Comportements à préserver

- Interface compacte, lisible sur iPhone et Mac, mode clair/sombre selon le système.
- Pas de titre introductif, de recherche, de compteur « X articles / 48 h », ni de bouton d’actualisation manuelle.
- Menu : BD, Sport, Tech, séparateur `/`, Fr, Us. Catégorie et langue se combinent ; Sport et français par défaut. Aucun onglet Tout ou Local.
- L’indicateur près de Sources affiche une icône d’actualisation et le temps depuis la collecte. Ce n’est pas un bouton et il ne lance aucune collecte.
- Articles triés du plus récent au plus ancien ; toute la ligne ouvre l’original dans un nouvel onglet avec `noopener noreferrer`.
- Sur mobile et ordinateur, icône, nom de la source et heure sont alignés sur une première ligne ; le titre vient en dessous sur toute la largeur et est limité à deux lignes.
- Tech et Sport : fenêtre glissante de 48 heures, côté collecteur ET interface.
- BD : dernière publication par source, sans expiration. Bouletcorp est actuellement la seule source BD classique.
- Mangas : dernier chapitre de chaque série, sans expiration, dans une section dédiée de BD indépendante de Fr / Us. Ne pas enregistrer de progression de lecture sans demande.
- Les données du navigateur se rechargent toutes les 5 minutes lorsque la page est visible et au retour sur l’onglet ; cela ne déclenche pas la collecte serveur.

## Collecte et sécurité

- Ne récupérer que titres, liens et métadonnées publiques ; pas de contenu intégral, de pages de chapitres, de contournement de connexion, de paywall ou de protection.
- Ne jamais inventer un titre, chapitre ou horodatage pour masquer un échec.
- Conserver les derniers résultats connus en cas d’échec suivant les règles de rétention, et signaler l’indisponibilité.
- MangaKatana : au moins 30 minutes entre vérifications d’une série, une seconde entre requêtes effectuées ; préserver ce ralentissement.
- Microsoft utilise un User-Agent explicite dans `sources.json`, nécessaire pour éviter certains refus HTTP.
- Les exécutions GitHub planifiées toutes les 5 minutes peuvent être retardées ou sautées. Ne pas promettre de délai garanti.
- Tout fichier du dépôt public peut être lu par un tiers. Ne jamais y ajouter de secrets, jetons ou identifiants personnels supplémentaires.
- Garder les favicons locaux et utiliser `textContent` pour les titres externes ainsi que la validation des URL HTTP(S).

## Validation

Depuis la racine du dépôt :

```sh
python3 -m unittest discover -s tests -v
node --check app.js
git diff --check
```

- Node sert uniquement à la vérification de syntaxe ; il n’est pas nécessaire au fonctionnement du site.
- Pour tester une collecte réelle : `python3 scripts/collect.py` et `python3 -m scripts.mangas`. Ces commandes utilisent le réseau et modifient les fichiers `data/` ; ne pas les lancer pendant la préparation automatique d’un environnement.
- Pour une prévisualisation : `python3 -m http.server 8080`.
- Pour toute modification d’interface, vérifier une largeur mobile (390 px, et idéalement 320 px), une largeur ordinateur, les filtres et l’absence d’erreur JavaScript. Vérifier les deux thèmes si les couleurs changent.
- Ajouter des tests ciblés aux collecteurs modifiés. Les tests unitaires doivent rester indépendants du réseau.

## Git et publication

- Examiner l’état Git avant modification. Le workflow ajoute régulièrement des commits de données sur `main` : récupérer les changements distants avant intégration, sans écraser le travail existant.
- Ne jamais forcer un push ni réécrire l’historique pour résoudre un conflit de données.
- Dans Codex Cloud, préparer les changements sur la branche de tâche et proposer une pull request, sauf instruction explicite de publication directe.
- Un push ou une fusion sur `main` déclenche la publication. Ne pas confondre une PR ouverte, un commit poussé et un site déployé.
- Avant d’annoncer « publié », confirmer le succès du workflow correspondant ; si impossible, préciser que la mise en ligne n’est pas vérifiée.
- Ne pas lancer le workflow de publication pour tester une branche : il récupère explicitement `main`.
