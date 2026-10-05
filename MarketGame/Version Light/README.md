# Market Game 2027 — version light

Couverture d'un portefeuille de fourniture pour l'annee de livraison 2027,
du coefficient de profil Enedis jusqu'a l'ordre day-ahead du 1er janvier 2027.

## Demarrage

```bash
python lancer.py --figures
```

Trente secondes environ. Tout ce qui est produit atterrit dans `sorties/`.
Sans `--figures`, les graphiques ne sont pas enregistres (le calcul est le meme).

Pour voir une figure a l'ecran, lance le script tout seul : `python spot_t3.py`.

## Le dossier

```
lancer.py                 lance toute la chaine dans l'ordre
Modelisation_Conso.py     1. la demande : profils Enedis, meteo, calendrier, volumes
scenarios.py              2. un scenario en detail (facultatif, pedagogique)
comparaison_scenarios.py  3. les scenarios, les strategies, le choix du T1
decision_t2.py            4. la revision du 01/12/2026 et la decision T2
spot_t3.py                5. le T3 du 31/12/2026 et l'ordre day-ahead
calendrier.py             bibliotheque : feries, types de jour, projection d'annee
figures.py                enregistre les sept figures en PNG

donnees/                  les fichiers du prof — le code n'y ecrit jamais
sorties/                  tout ce que le code produit — effacable sans risque
rapport/                  le document explicatif, en Word et en PDF
```

Chaque script est independant : il reconstruit tout depuis `donnees/`, aucun ne lit
les sorties d'un autre. On peut donc en relancer un seul apres avoir change un parametre.

## Ce qu'il faut mettre dans donnees/

```
RES1_BASE.csv                     coefficients de profil Enedis RES1
PRO1_BASE.csv                     coefficients de profil Enedis PRO1
gradients.csv                     gradients des profils dynamiques
temperature_2025.csv              temperature realisee et normale lissees
historique/temperature_2021.csv   ... jusqu'a _2024.csv
historique/prix_2021.csv          ... jusqu'a _2024.csv, day-ahead ENTSO-E
```

Si ces fichiers sont restes a cote des scripts (ancienne disposition), le code les
y trouve quand meme : `donnees/` est essaye en premier, le dossier courant ensuite.

## Les parametres, et ou les changer

| Quoi | Ou |
| --- | --- |
| Effectifs commerciaux aux trois jalons | `CLIENTS`, en tete de `Modelisation_Conso.py` |
| Prix EEX (Base/Peak, Cal, Q1-Q4, Jan-Jun, aux trois jalons) | `EEX`, en tete de `scenarios.py` |
| Annees de scenario retenues | `ANNEES`, en tete de `comparaison_scenarios.py` |
| Strategies testees, choc fondamental, alpha | en tete de `comparaison_scenarios.py` |
| Previsions du 1er janvier 2027, position detenue, prix de clearing | en tete de `spot_t3.py` |

Imposes par le Conseil (section 2.2 des guidelines) : prix de vente 95 EUR/MWh,
marge cible 10, plancher de risque 5, prime de risque forward 3 %.

Deux constantes attendent encore une information du prof, et valent `None` :
`SOLAIRE_ANNUEL_MWH` (la centrale de 80 MWc produit-elle toute l'annee ?) et
`PRIX_CLEARING` (le prix spot publie, pour calculer le hedge success).

## Le rapport

`rapport/` contient le document qui explique les quinze etapes, la theorie du cours
d'un cote et le bout de code qui l'applique de l'autre, avec les sept figures.
