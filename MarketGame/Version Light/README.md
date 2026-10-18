# Market Game 2027 — version light

Couverture d'un portefeuille de fourniture pour l'annee de livraison 2027,
du coefficient de profil Enedis jusqu'a l'ordre day-ahead du 1er janvier 2027.

## Lancer

Le depot contient le code **et** les donnees : un clone frais tourne tel quel.

```bash
pip install pandas numpy matplotlib     # une seule fois
cd "MarketGame/Version Light"
python lancer.py --figures
```

Trente secondes. Tout ce qui est produit atterrit dans `sorties/`, qui est
effacable sans risque. Pour voir une figure a l'ecran, lance un script tout
seul : `python t3_spot.py`.

## Les donnees

Les douze CSV du prof sont **deja versionnes** : quatre a la racine de
`donnees/` (`RES1_BASE`, `PRO1_BASE`, `gradients`, `temperature_2025`) et huit
dans `donnees/historique/` (`temperature_` et `prix_` de 2021 a 2024). Il n'y a
rien a installer. Ses Excel et ses PDF sont dans `donnees/sources/`, que **le
code ne lit jamais** — les prix EEX qui servent au calcul sont recopies a la
main dans la table `EEX` de `outils/marche.py`.

## Tout le reste

Carte du dossier, role de chaque fichier, ou changer quel parametre, ce que
produit chaque execution, les limites du modele :

`rapport/` — voir `rapport/LISEZMOI.md` pour les quatre documents et leurs liens.
