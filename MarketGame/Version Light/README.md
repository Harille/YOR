# Market Game 2027 — version light

Couverture d'un portefeuille de fourniture pour l'annee de livraison 2027,
du coefficient de profil Enedis jusqu'a l'ordre day-ahead du 1er janvier 2027.

## Demarrage

```bash
python lancer.py --figures
```

Trente secondes. Tout ce qui est produit atterrit dans `sorties/`.
Pour voir une figure a l'ecran, lance un script tout seul : `python t3_spot.py`.

## Trois codes, un par jalon

C'est la structure du cours : le meme travail, refait a chaque jalon avec des
donnees actualisees. Les trois fichiers appellent **les memes fonctions** de
`outils/` — seules les donnees et les prix changent.

| Fichier | Jalon | Ce qu'il fait |
| --- | --- | --- |
| `t1_strategie.py` | 22/09/2026 | construire la demande, les scenarios, les strategies ; choisir la meilleure ; l'executer |
| `t2_decision.py` | 01/12/2026 | actualiser les donnees ; demande nette avec hedging actualise ; faire evoluer la strategie ; l'executer |
| `t3_spot.py` | 31/12/2026 | actualiser les donnees ; demande nette = open positions ; hedging ; envoyer les ordres SPOT |

Ouvre les trois cote a cote : ils suivent les memes points, dans le meme ordre,
avec les memes bandeaux de section.

## Le moteur, partage par les trois

| Fichier | Contenu |
| --- | --- |
| `outils/calendrier.py` | feries, types de jour, projection d'une annee sur une autre |
| `outils/demande.py` | profils Enedis, thermosensibilite, courbe de charge, volumes |
| `outils/marche.py` | prix EEX aux trois jalons, scenarios de prix, methode alpha |
| `outils/couverture.py` | produits, mix de couverture, marge, strategies, scenarios |

T1, T2 et T3 empruntent **26 fonctions et constantes** a ces quatre fichiers.
C'est ce qui garantit que le calcul est identique aux trois jalons.

## Le dossier

```
lancer.py                 lance les trois jalons dans l'ordre
figures.py                enregistre les sept figures en PNG
README.md                 ce fichier

t1_strategie.py           T1 - 22/09/2026
t2_decision.py            T2 - 01/12/2026
t3_spot.py                T3 - 31/12/2026

outils/                   le moteur, partage par les trois jalons
donnees/                  les fichiers du prof - le code n'y ecrit jamais
sorties/                  tout ce que le code produit - effacable sans risque
rapport/                  le document explicatif, en Word et en PDF
```

Chaque fichier commence par un en-tete qui dit ce qu'il fait, ce qu'il lit, ce
qu'il ecrit, quels parametres s'y changent et quelles etapes du rapport il couvre.

## Ce qu'il faut mettre dans donnees/

```
RES1_BASE.csv                     coefficients de profil Enedis RES1
PRO1_BASE.csv                     coefficients de profil Enedis PRO1
gradients.csv                     gradients des profils dynamiques
temperature_2025.csv              temperature realisee et normale lissees
historique/temperature_2021.csv   ... jusqu'a _2024.csv
historique/prix_2021.csv          ... jusqu'a _2024.csv, day-ahead ENTSO-E
```

Si ces fichiers sont restes a la racine (ancienne disposition), le code les y
trouve quand meme : `donnees/` est essaye en premier, la racine ensuite.

### Et les Excel et les PDF du prof ?

Ils vont dans `donnees/sources/`. **Le code ne les lit jamais** : leurs chiffres
ont ete recopies a la main dans des constantes (la table `EEX`, `CLIENTS`,
`T_PREVUE`, `SOLAIRE`...). `donnees/sources/LISEZMOI.txt` dit quelle constante
vient de quel document — c'est ce fichier qu'on ouvre quand le prof publie une
mise a jour, pour savoir quoi changer et ou.

## Ou changer quoi

| Quoi | Ou |
| --- | --- |
| Effectifs commerciaux aux trois jalons | `CLIENTS`, en tete de `outils/demande.py` |
| Prix EEX releves par le prof | `EEX`, en tete de `outils/marche.py` |
| Prix de vente, marge cible, plancher de risque | en tete de `outils/couverture.py` |
| Strategies testees, annees de scenario, choc, alpha | en tete de `outils/couverture.py` |
| Strategie retenue au T1, options testees au T2 | en tete de `t2_decision.py` |
| Prevision du 1er janvier, position detenue, prix de clearing | en tete de `t3_spot.py` |

Imposes par le Conseil (section 2.2 des guidelines) : prix de vente 95 EUR/MWh,
marge cible 10, plancher de risque 5, prime de risque forward 3 %.

Deux constantes attendent encore une information du prof, et valent `None` :
`SOLAIRE_ANNUEL_MWH` (la centrale de 80 MWc produit-elle toute l'annee ?) et
`PRIX_CLEARING` (le prix spot publie, pour calculer le hedge success).

## Le rapport

`rapport/` contient le document qui explique les quinze etapes, la theorie du
cours d'un cote et le bout de code qui l'applique de l'autre, avec les sept
figures produites par `figures.py`.
