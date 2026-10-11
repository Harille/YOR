# Market Game 2027 — version light

Couverture d'un portefeuille de fourniture pour l'annee de livraison 2027,
du coefficient de profil Enedis jusqu'a l'ordre day-ahead du 1er janvier 2027.

## Lancer

```bash
python lancer.py --figures
```

Trente secondes. Tout ce qui est produit atterrit dans `sorties/`, qui est
effacable sans risque. Pour voir une figure a l'ecran, lance un script tout
seul : `python t3_spot.py`.

## Installer les donnees

Les douze CSV du prof vont dans `donnees/` : quatre a la racine (`RES1_BASE`,
`PRO1_BASE`, `gradients`, `temperature_2025`) et huit dans
`donnees/historique/` (`temperature_` et `prix_` de 2021 a 2024). Ses Excel et
ses PDF vont dans `donnees/sources/`, que **le code ne lit jamais**.

## Tout le reste

Carte du dossier, role de chaque fichier, ou changer quel parametre, ce que
produit chaque execution, les limites du modele :

`rapport/Market Game 2027 - comprendre le code etape par etape.pdf`
