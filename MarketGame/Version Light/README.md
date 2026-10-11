# Market Game 2027 — version light

Couverture d'un portefeuille de fourniture pour l'annee de livraison 2027,
du coefficient de profil Enedis jusqu'a l'ordre day-ahead du 1er janvier 2027.

## Demarrage

```bash
python lancer.py --figures
```

Trente secondes. Tout ce qui est produit atterrit dans `sorties/`.
Pour voir une figure a l'ecran, lance un script tout seul : `python t3_spot.py`.

## Le dossier

```
lancer.py                 lance les trois jalons dans l'ordre
figures.py                enregistre les sept figures en PNG

t1_strategie.py           T1 - 22/09/2026  strategie
t2_decision.py            T2 - 01/12/2026  decision
t3_spot.py                T3 - 31/12/2026  ordres SPOT

outils/                   le moteur, partage par les trois jalons
donnees/                  les fichiers du prof - le code n'y ecrit jamais
sorties/                  tout ce que le code produit - effacable sans risque
rapport/                  les documents explicatifs, en Word et en PDF
```

Chaque fichier commence par un en-tete qui dit ce qu'il fait, ce qu'il lit, ce
qu'il ecrit et quels parametres s'y changent. Le detail du raisonnement, jalon
par jalon, est dans `rapport/` (« Market Game 2027 - comprendre le code etape
par etape », en Word et en PDF).

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

Les Excel et les PDF du prof vont dans `donnees/sources/`. **Le code ne les lit
jamais** : leurs chiffres sont recopies a la main dans des constantes.
`donnees/sources/LISEZMOI.txt` dit quelle constante vient de quel document —
c'est ce fichier qu'on ouvre quand le prof publie une mise a jour.

## Deux chiffres qui ne viennent pas du prof

`PRIX_CLEARING` (`t3_spot.py`) vaut `None` : le prix spot du 1er janvier se
forme pendant l'enchere, le hedge success se calcule apres.
`SOLAIRE_ANNUEL_MWH` vaut 96 000 MWh (80 MWc x 1 200 kWh/kWc) — **notre
hypothese**, et le parametre le plus lourd du T3 ; sa repartition par trimestre
suit un profil PV reel (`PART_SOLAIRE_TRIMESTRE` : 15 / 33 / 34 / 18 %).
