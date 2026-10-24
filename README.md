# Actu

Un fil personnel, compact et sans publicité ajoutée : tech et sport des dernières 48 heures, dernières publications BD et derniers chapitres des mangas suivis sans limite de date.

**Application : https://thomasroehm.github.io/actu/**

## Utilisation

- Sur iPhone : ouvrir le lien dans Safari, puis Partager → Sur l’écran d’accueil.
- Sur Mac : ouvrir le même lien et l’ajouter aux favoris.
- Le thème clair/sombre suit automatiquement le système.
- Chaque ligne ouvre l’article original dans un nouvel onglet. Les liens visités sont atténués par le navigateur.
- Le fil s’ouvre sur les sources françaises. Les boutons Français / Anglais séparent les langues et se combinent avec Tout / Tech / Sport / BD. Le tri reste du plus récent au plus ancien. La recherche a été supprimée.
- « Les sources » affiche le résultat de la dernière collecte. Une source sans publication récente n’est pas une erreur.
- Les données publiées se rechargent automatiquement toutes les 5 minutes lorsque la page est visible, ainsi qu’au retour sur l’onglet. Cela ne déclenche pas de collecte serveur.

## Collecte et publication

GitHub Actions programme `scripts/collect.py` toutes les 5 minutes, aux minutes 02, 07, 12, 17, 22, 27, 32, 37, 42, 47, 52 et 57 de chaque heure, ainsi qu’après un push sur `main` ou un lancement manuel. GitHub peut retarder ou sauter des déclenchements : cet intervalle n’est pas garanti.

Les 23 sources configurées utilisent leurs flux RSS/Atom lorsqu’ils existent, notamment Apple Newsroom en français et Microsoft Blog en anglais. NBA et NFL utilisent les métadonnées publiques intégrées à leurs pages. Digital Minimalist utilise les titres et dates de publication des 12 premiers articles liés depuis son blog. Actu.fr Grand Bourgtheroulde apparaît dans Local / Fr et Tout / Fr, avec une rétention de 48 heures : seuls les 12 premiers liens uniques d’articles de cette commune sont consultés pour leurs titres et dates de publication publiques. Aucun article complet n’est copié, aucun accès payant n’est contourné.

Les articles sont fusionnés avec `data/articles.json`, dédoublonnés par URL et conservés pendant 48 heures selon leur date de publication. Pour les sources BD, seule la dernière publication est conservée, sans expiration. Les dates absentes ou ambiguës sont ignorées. En cas d’échec d’une source, ses articles déjà collectés sont conservés selon ces règles. Une panne de toutes les sources bloque la publication.

Les 29 mangas de `mangas.json` sont affichés dans une section dédiée de BD, indépendamment du filtre Fr / Us. `python3 -m scripts.mangas` récupère uniquement le premier chapitre de la table publique de chaque série sur MangaKatana, jamais les pages du chapitre. La vérification est espacée d’au moins 30 minutes par série, avec une seconde entre requêtes. `data/mangas.json` conserve le dernier résultat sans expiration ; les erreurs sont signalées et ne suppriment pas les chapitres connus. Les dates inconnues ne sont pas inventées. La sélection est publique, mais la progression de lecture fournie par l’utilisateur n’est pas enregistrée.

Au premier lancement, la couverture historique dépend du nombre d’articles exposés par chaque flux/page. Elle se complète au fil des collectes ; un flux limité ou une interruption prolongée peut laisser des articles manquants. Les adaptateurs de pages peuvent nécessiter une mise à jour si les sites changent.

Chaque collecte enregistre les données dans Git pour les préserver entre exécutions. Le commit produit par `GITHUB_TOKEN` ne déclenche pas un autre workflow. Les exécutions planifiées peuvent être désactivées par GitHub après une longue inactivité du dépôt ; vérifier l’onglet Actions si la date de collecte devient ancienne.

GitHub Pages doit utiliser **GitHub Actions** comme source de publication. Le site et les données sont publics. Le dossier `dist/` est créé pendant le workflow et ne contient que les fichiers nécessaires au site.

## Développement

Python 3.9+ et un navigateur récent suffisent, sans dépendance Python ou JavaScript.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/collect.py
python3 -m http.server 8080
```

Ouvrir `http://localhost:8080`. Les sources se configurent dans `sources.json`. Pour renouveler les favicons, lancer `python3 scripts/icons.py` ; ils sont ensuite servis localement, sans requête vers Google à chaque consultation.

Les tests vérifient les dates, les fuseaux horaires, la rétention sur 48 heures, les doublons, les liens RSS/Atom, les métadonnées NFL et le filtrage BeBasket.
