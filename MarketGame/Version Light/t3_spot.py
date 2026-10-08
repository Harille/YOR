"""
T3 — 31/12/2026 : ACTUALISER, REEQUILIBRER, ENVOYER LES ORDRES SPOT
...............................................................................
Le plan du cours, point par point :
    1. actualiser les donnees
    2. demande nette  =>  open positions
    3. hedging (reequilibrage trimestriel aux prix du 31/12/2026)
    4. envoyer les ordres SPOT pour le 1er janvier 2027

Ce que ca lit   : donnees/*.csv, les prix EEX du 31/12/2026 (table EEX), et la
                  prevision du 1er janvier donnee en tete de ce fichier
Ce que ca ecrit : sorties/t3_reequilibrage.csv, sorties/t3_position_20270101.csv,
                  sorties/t3_ordres_spot_20270101.csv (le formulaire EPEX)
Duree           : ~2 s
A changer ici   : T_PREVUE et SOLAIRE (la prevision du 1er janvier),
                  HEURE_SPOT, PRIX_CLEARING. Ce qui est deja achete se
                  change dans outils/position.py (ACHETE).
A savoir        : PRIX_CLEARING vaut None et le restera jusqu'a la seance :
                  le prix sort de l'enchere, il n'est publie nulle part avant.
Dans le rapport : etape 15
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from outils import calendrier
from outils import couverture as cv
from outils import marche
from outils import position
from outils.demande import CLIENTS, SORTIES, calculer_puissances, construire_base, reviser

JOUR = "2027-01-01"
HEURE_SPOT = 14            # l'heure demandee par le prof : 14h-15h

# Previsions du 31/12/2026 (fichier 26_EM_5_Data_forecast_for_1st_January_2027_T3)
T_PREVUE = [0.5, 0, -0.5, -1, -1.5, -2, -2, -1.5, -0.5, 1, 2.5, 3.5,
            4, 4, 3.5, 2.5, 1.5, 1, 0.5, 0, -0.5, -1, -1.5, -2]
SOLAIRE = [0, 0, 0, 0, 0, 0, 0, 0, 2, 8, 15, 21,
           24, 21, 14, 5, 0.5, 0, 0, 0, 0, 0, 0, 0]
SOLAIRE_MWC = 80

# Le Conseil (exercice SPOT, 1.1) confirme la centrale operationnelle "from 1 January
# 2027" et demande de l'integrer "for 2027 and subsequent years" : elle produit donc
# toute l'annee, pas seulement le 1er janvier. Le prof ne donne pas le productible
# annuel -> c'est NOTRE hypothese, a assumer comme telle.
PRODUCTIBLE_KWH_PAR_KWC = 1200             # France metropolitaine, ordre de grandeur usuel
SOLAIRE_ANNUEL_MWH = SOLAIRE_MWC * PRODUCTIBLE_KWH_PAR_KWC    # 80 MWc x 1 200 = 96 000 MWh

# Le solaire ne produit pas au rythme de la consommation : il faut le repartir par
# saison, pas au prorata du besoin, sinon on lui prete de l'energie en hiver.
PART_SOLAIRE_TRIMESTRE = {1: 0.15, 2: 0.33, 3: 0.34, 4: 0.18}

COUT_MARGINAL_SOLAIRE = 0.0

# Conventions du formulaire EPEX (exercice SPOT, point 2). Elles ne sont PAS
# interchangeables : une limite a +4 000 sur une VENTE signifie qu'on ne vend jamais.
PRIX_ACHAT_ILLIMITE = 4000.0     # achat price-independent
PRIX_VENTE_ILLIMITE = -600.0     # vente price-independent

POSITION = position.ACHETE   # ce qui est deja achete au 31/12 : voir outils/position.py

PRIX_CLEARING = None       # prix spot 14h-15h, publie par le prof apres la session 5


def volumes(base, jalon):
    """Volume 2027 a temperature normale, par trimestre, pour un jalon commercial."""
    d = calculer_puissances(calendrier.projeter(base, 2027))
    p = reviser(d, jalon)["P_totale_kW"]
    return (p.groupby(np.asarray(p.index.quarter)).sum() * 0.25 / 1000), d


def objectif_1(d, vq):
    """Reequilibrer la couverture aux prix du 31/12."""
    index = d["P_totale_kW"].resample("h").mean().index
    heures = {(p, n): cv.heures_livrees(p, n, index) for (p, n) in POSITION}

    lignes, livre = [], {q: 0.0 for q in vq}
    for (produit, nature), (mw, jalon) in sorted(POSITION.items()):
        e = mw * heures[(produit, nature)]
        achat, t3 = marche.prix_eex(produit, nature, jalon), marche.prix_eex(produit, nature, "T3")
        lignes.append({"produit": produit, "MW": mw, "achete au": jalon, "MWh": e,
                       "prix paye": achat, "prix T3": t3,
                       "MtM kEUR": e * (t3 - achat) / 1000})
        fen = cv.fenetre(produit, nature, index).to_numpy()
        for q in vq:                              # part livree a l'interieur du trimestre q
            livre[q] += mw * float((fen & (np.asarray(index.quarter) == q)).sum())
    portefeuille = pd.DataFrame(lignes)
    cv.afficher(portefeuille.round(2), "POSITION DETENUE, VALORISEE AU 31/12/2026")
    e_tot, mtm = portefeuille["MWh"].sum(), portefeuille["MtM kEUR"].sum()
    print(f"  total {e_tot:,.0f} MWh | prix moyen paye "
          f"{(portefeuille['MWh'] * portefeuille['prix paye']).sum() / e_tot:.2f} EUR/MWh"
          f" | mark-to-market {mtm / 1000:+.2f} MEUR")

    besoin = {q: vq[q] for q in vq}
    if SOLAIRE_ANNUEL_MWH:                       # besoin NET de la production propre
        for q in besoin:
            besoin[q] -= SOLAIRE_ANNUEL_MWH * vq[q] / sum(vq.values())
        print(f"  besoin net de {SOLAIRE_ANNUEL_MWH:,.0f} MWh de production solaire")

    lignes = []
    for q in sorted(besoin):
        produit = f"Q{q}-27"
        h = cv.heures_livrees(produit, "Base", index)
        ecart = besoin[q] - livre[q]
        prix = marche.prix_eex(produit, "Base", "T3")
        lignes.append({"trimestre": produit, "besoin MWh": besoin[q], "couvert MWh": livre[q],
                       "ratio %": 100 * livre[q] / besoin[q], "ecart MWh": ecart,
                       "a traiter MW": ecart / h, "prix T3": prix,
                       "montant kEUR": ecart * prix / 1000})
    action = pd.DataFrame(lignes).set_index("trimestre")
    cv.afficher(action.round(2), "OBJECTIF 1 - REEQUILIBRAGE PAR TRIMESTRE")
    b_tot, brut = sum(besoin.values()), sum(vq.values())
    print(f"  besoin {b_tot:,.0f} MWh | couvert {e_tot:,.0f} MWh"
          f" -> ratio global {100 * e_tot / b_tot:.1f} %")
    if SOLAIRE_ANNUEL_MWH:
        print(f"  sans deduire le solaire, le besoin serait de {brut:,.0f} MWh"
              f" et le ratio de {100 * e_tot / brut:.1f} % :")
        print("  c'est la deduction du solaire qui fait passer de sous-couvert a sur-couvert.")
        print("  Reserve : le solaire produit aux heures creuses d'ete, son energie ne vaut")
        print("  donc pas le prix moyen du trimestre. Deduire MWh pour MWh est une")
        print("  approximation genereuse ; un taux de captation l'affinerait.")
    for _, r in action.iterrows():
        sens = "ACHETER" if r["ecart MWh"] > 0 else "VENDRE "
        print(f"  {sens} {abs(r['a traiter MW']):5.2f} MW de {r.name} Base"
              f" a {r['prix T3']:6.2f} -> {r['montant kEUR']:+8.1f} kEUR")
    print(f"  solde de l'operation : {action['montant kEUR'].sum() / 1000:+.2f} MEUR")
    return action


def journee(base):
    """Charge du 1er janvier avec la temperature prevue et les effectifs du T3."""
    cible = calendrier.projeter(base, 2027)
    j = cible[np.asarray(cible.index.date) == pd.Timestamp(JOUR).date()].copy()
    pas = len(j) // 24
    j["temperature_realisee_lissee_degc"] = np.repeat(T_PREVUE, pas)[:len(j)]
    j = calculer_puissances(j, "T3")      # meme formule qu'au T1 et au T2, effectifs du T3

    h = pd.DataFrame({"charge MW": j["P_dyn_totale_kW"].resample("h").mean() / 1000,
                      "charge normale MW": j["P_totale_kW"].resample("h").mean() / 1000})
    h["solaire MW"] = SOLAIRE
    h["couverture MW"] = sum(mw * cv.fenetre(p, n, h.index)
                             for (p, n), (mw, _) in POSITION.items())
    h["position MW"] = h["charge MW"] - h["solaire MW"] - h["couverture MW"]
    h["sens"] = np.where(h["position MW"] > 0, "SHORT (acheter)", "LONG (revendre)")
    return j, h


def ordre_spot(h, heure=HEURE_SPOT):
    """Les 24 ordres du formulaire EPEX : un volume et un prix limite par heure.

    Convention du formulaire : volume positif = achat, negatif = vente.
    Le prix limite n'est pas un prix qu'on propose, c'est le maximum qu'on accepte
    de payer (ou le minimum qu'on accepte de recevoir). Le prix de clearing sort de
    l'enchere : il ne se decide pas ici.
    """
    lignes = []
    for i, (_, r) in enumerate(h.iterrows()):
        volume = r["position MW"]                 # une heure : 1 MW = 1 MWh
        if volume > 0:
            prix, motif = PRIX_ACHAT_ILLIMITE, "achat subi : l'imbalance coute plus cher"
        else:
            # Un surplus de forward est deja paye et sera livre : il faut s'en defaire.
            # Un surplus de solaire, lui, se coupe pour rien -> il porte son cout marginal.
            solaire_vendable = min(r["solaire MW"], -volume)
            if solaire_vendable > 0 and solaire_vendable >= -volume - 1e-9:
                prix, motif = COUT_MARGINAL_SOLAIRE, "surplus solaire : coupable sans cout"
            else:
                prix, motif = PRIX_VENTE_ILLIMITE, "surplus de forward : deja paye, a ecouler"
        lignes.append({"heure": f"{i:02d}:00-{i + 1:02d}:00",
                       "charge MW": r["charge MW"], "couverture MW": r["couverture MW"],
                       "solaire MW": r["solaire MW"],
                       "volume MWh": round(float(volume), 2),
                       "prix limite EUR/MWh": prix,
                       "sens": "ACHAT" if volume > 0 else "VENTE", "motif": motif})
    ordres = pd.DataFrame(lignes).set_index("heure")

    cv.afficher(ordres.drop(columns=["motif"]).round(2),
                f"OBJECTIF 2 - LES 24 ORDRES DU {pd.Timestamp(JOUR):%d/%m/%Y}")
    achats = ordres[ordres["volume MWh"] > 0]
    ventes = ordres[ordres["volume MWh"] < 0]
    print(f"  {len(achats)} heures d'achat pour {achats['volume MWh'].sum():,.1f} MWh,"
          f" {len(ventes)} heures de vente pour {-ventes['volume MWh'].sum():,.1f} MWh")
    print(f"  prix limite {PRIX_ACHAT_ILLIMITE:,.0f} sur les achats,"
          f" {PRIX_VENTE_ILLIMITE:,.0f} sur les ventes : price-independent des deux cotes."
          f" Les deux ne sont pas interchangeables.")

    peak = sum(1 for (_, nature) in POSITION if nature == "Peak")
    fin = ("ATTENTION : le peak EEX inclut les jours feries, il livre donc le 1er janvier"
           if peak else "aucun -> le piege du vendredi ferie ne nous concerne pas")
    print(f"  produits Peak detenus : {peak} -> {fin}")

    print("")
    print("  Les deux lignes de justification a recopier sur le formulaire :")
    print("    Tous les achats sont price-independent : la consommation a lieu quoi qu'il")
    print("    arrive, et l'energie non achetee se regle au prix de desequilibre, en regle")
    print("    generale superieur au spot. Les ventes ecoulent un surplus de forward deja")
    print(f"    paye ; le solaire porterait, lui, une limite a {COUT_MARGINAL_SOLAIRE:.0f}"
          f" EUR/MWh - on le coupe")
    print("    plutot que de payer pour l'injecter - mais il ne produit a aucune heure longue.")

    r = h.iloc[heure]
    o = ordres.iloc[heure]
    print("")
    print(f"  Focus sur l'heure demandee, {heure:02d}h00-{heure + 1:02d}h00 :")
    print(f"    charge {r['charge MW']:.2f} - solaire {r['solaire MW']:.2f}"
          f" - couverture {r['couverture MW']:.2f} = {r['position MW']:+.2f} MW")
    print(f"    ordre : {o['sens']} {abs(o['volume MWh']):.2f} MWh"
          f" a {o['prix limite EUR/MWh']:,.0f} EUR/MWh")

    if PRIX_CLEARING is None:
        print("")
        print("  PRIX_CLEARING non renseigne : le prix sort de l'enchere en seance.")
        print("  Le hedge success se calcule une fois le clearing connu.")
    else:
        cout = float((ordres["volume MWh"] * PRIX_CLEARING).sum())
        cout_nu = float(((h["charge MW"] - h["solaire MW"]) * PRIX_CLEARING).sum())
        print("")
        print(f"  prix de clearing   {PRIX_CLEARING:7.2f} EUR/MWh")
        print(f"  cout de la journee {cout:+12,.0f} EUR"
              f"  (sans aucune couverture : {cout_nu:+,.0f} EUR)")
        print(f"  hedge success      {cout_nu - cout:+12,.0f} EUR")
    return ordres


def main():
    # ==========================================================================
    # T3 - POINT 1 : ACTUALISER LES DONNEES
    # effectifs du 31/12, prix EEX du 31/12, prevision du 1er janvier
    # ==========================================================================
    base = construire_base()
    vq, d = volumes(base, "T3")
    print(f"\n{'=' * 78}\nT3 - 31 DECEMBRE 2026\n{'=' * 78}")
    for jalon in CLIENTS:
        v, _ = volumes(base, jalon)
        print(f"  volume 2027 au {jalon} : {v.sum():>9,.0f} MWh"
              f"   ({CLIENTS[jalon]['RES1']:,} RES1 + {CLIENTS[jalon]['PRO1']:,} PRO1)")

    # ==========================================================================
    # T3 - POINTS 2 ET 3 : DEMANDE NETTE => OPEN POSITIONS, PUIS HEDGING
    # ==========================================================================
    action = objectif_1(d, vq.to_dict())
    j, h = journee(base)

    aff = h.copy()
    aff.index = [f"{x:%H:%M}" for x in aff.index]
    cv.afficher(aff.round(2), f"POSITION OUVERTE DU {pd.Timestamp(JOUR):%d/%m/%Y}"
                              f" - temperature prevue, solaire deduit")
    print(f"  temperature prevue {np.mean(T_PREVUE):+.2f} C contre"
          f" {j['temperature_normale_lissee_degc'].mean():.2f} C de normale")
    print(f"  charge {h['charge MW'].sum():,.1f} MWh (a temperature normale :"
          f" {h['charge normale MW'].sum():,.1f}) | solaire {h['solaire MW'].sum():,.1f} MWh"
          f" ({SOLAIRE_MWC} MWc)")
    print(f"  a acheter {h['position MW'].clip(lower=0).sum():,.1f} MWh"
          f" | a revendre {-h['position MW'].clip(upper=0).sum():,.1f} MWh")

    # ==========================================================================
    # T3 - POINT 4 : ENVOYER LES ORDRES SPOT
    # ==========================================================================
    ordres = ordre_spot(h)
    action.to_csv(SORTIES / "t3_reequilibrage.csv", sep=";", decimal=",")
    h.to_csv(SORTIES / "t3_position_20270101.csv", sep=";", decimal=",")
    ordres.to_csv(SORTIES / "t3_ordres_spot_20270101.csv", sep=";", decimal=",")
    print("\n-> Exports dans sorties/ : t3_reequilibrage.csv, t3_position_20270101.csv,"
          " t3_ordres_spot_20270101.csv")
    return action, h


def tracer(h):
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    x = range(len(h))
    axes[0].plot(x, h["charge MW"], lw=2, color="tab:green", label="charge (T prevue)")
    axes[0].plot(x, h["charge normale MW"], lw=1, ls="--", color="grey", label="charge (T normale)")
    axes[0].step(x, h["couverture MW"], where="mid", lw=2, color="tab:red", label="couverture")
    axes[0].bar(x, h["solaire MW"], color="tab:orange", alpha=0.5, label="solaire")
    axes[0].set_ylabel("MW"); axes[0].legend(fontsize=8)
    axes[0].set_title(f"{JOUR} - charge, couverture et production propre")

    v = h["position MW"]
    axes[1].bar(x, v, color=np.where(v > 0, "tab:red", "tab:blue"))
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].axvspan(HEURE_SPOT - 0.5, HEURE_SPOT + 0.5, color="gold", alpha=0.3)
    axes[1].set_ylabel("MW"); axes[1].set_xlabel("heure")
    axes[1].set_title("Position ouverte : rouge = acheter, bleu = revendre"
                      f" (en jaune, l'heure {HEURE_SPOT:02d}h-{HEURE_SPOT + 1:02d}h)")
    for ax in axes:
        ax.set_xticks(list(x)); ax.set_xticklabels([f"{i:02d}" for i in x], fontsize=7)
        ax.grid(alpha=0.3)
    fig.tight_layout(); plt.show()


if __name__ == "__main__":
    tableau, position = main()
    tracer(position)
