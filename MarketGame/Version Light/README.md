# Market Game - Hedging for 2027 (version light)

Ordre d'execution :

1. `Modelisation_Conso.py`  - etape 1 : courbe de charge 2027 a temperature normale,
   volumes mensuels, trimestriels, split peak/off-peak, portefeuille T1 et T2
2. `scenarios.py`           - un seul scenario (annee definie par `ANNEE_HISTORIQUE`)
3. `comparaison_scenarios.py` - etapes 2 a 5 : scenarios, pente b, methode alpha,
   mix de produits EEX, marges, choix de la strategie T1, sensibilites
4. `decision_t2.py`         - sections 4 et 5 : anticipation contre realite, revision
   des probabilites et du volume, mark-to-market, decision T2, position ouverte du 01/01/2027
5. `spot_t3.py`             - T3 (31/12/2026) : reequilibrage trimestriel aux prix du 31/12,
   position ouverte du 01/01/2027 avec temperature prevue et production solaire,
   courbe d'ordre day-ahead pour 14h-15h

`calendrier.py` est une bibliotheque (feries, appariement par type de jour, projection).

## Fichiers de donnees attendus

```
RES1_BASE.csv            coefficients de profil Enedis RES1
PRO1_BASE.csv            coefficients de profil Enedis PRO1
gradients.csv            gradients des profils dynamiques
temperature_2025.csv     temperature realisee et normale lissees
historique/temperature_2021.csv ... _2024.csv
historique/prix_2021.csv ... _2024.csv       day-ahead ENTSO-E
```

## Parametres imposes par le Conseil (section 2.2 des guidelines)

prix de vente 95 EUR/MWh, marge cible 10, plancher de risque 5, prime de risque forward 3 %.

## Prix EEX

Table `EEX` dans `scenarios.py` : Base et Peak, Cal / Q1-Q4 / Jan-Jun,
aux trois jalons - 22/09/2026 (T1), 01/12/2026 (T2) et 31/12/2026 (T3).

## Effectifs commerciaux

Dictionnaire `CLIENTS` dans `Modelisation_Conso.py` : 200 000 / 5 000 au T1,
188 200 / 4 585 au T2, 191 531 / 4 745 au T3.

## Previsions du 1er janvier 2027

En tete de `spot_t3.py` : temperature horaire prevue, production solaire horaire
(centrale de 80 MWc), position deja detenue, et `PRIX_CLEARING` a renseigner
une fois le prix spot publie.
