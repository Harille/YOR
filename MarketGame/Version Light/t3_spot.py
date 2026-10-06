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
Ce que ca ecrit : sorties/t3_reequilibrage.csv,
                  sorties/t3_position_20270101.csv
Duree           : ~2 s
A changer ici   : T_PREVUE et SOLAIRE (la prevision du 1er janvier), POSITION
                  (ce qui est deja achete), HEURE_SPOT, PRIX_CLEARING
Deux inconnues  : SOLAIRE_ANNUEL_MWH et PRIX_CLEARING valent None tant que le
                  prof n'a pas donne l'information.
Dans le rapport : etape 15
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from outils import calendrier
from outils import couverture as cv
from outils import marche
from outils.demande import (CLIENTS, SORTIES, PARAMS, calculer_puissances,
                                coefficient_meteo, construire_base, fud, _totaliser)

JOUR = "2027-01-01"
HEURE_SPOT = 14            # l'heure demandee par le prof : 14h-15h

# Previsions du 31/12/2026 (fichier 26_EM_5_Data_forecast_for_1st_January_2027_T3)
T_PREVUE = [0.5, 0, -0.5, -1, -1.5, -2, -2, -1.5, -0.5, 1, 2.5, 3.5,
            4, 4, 3.5, 2.5, 1.5, 1, 0.5, 0, -0.5, -1, -1.5, -2]
SOLAIRE = [0, 0, 0, 0, 0, 0, 0, 0, 2, 8, 15, 21,
           24, 21, 14, 5, 0.5, 0, 0, 0, 0, 0, 0, 0]
SOLAIRE_MWC = 80
SOLAIRE_ANNUEL_MWH = None  # inconnu : le prof ne fournit que le 1er janvier.
                           # Renseigner pour que l'objectif 1 raisonne en besoin NET.
COUT_MARGINAL_SOLAIRE = 0.0

POSITION = {               # ce qui est deja achete au 31/12 : un fait, pas une decision
    ("Q1-27", "Base"): (49.58, "T1"),
    ("Q2-27", "Base"): (37.91, "T1"),
    ("Q3-27", "Base"): (36.47, "T1"),
    ("Q4-27", "Base"): (47.65, "T1"),
    ("Cal-27", "Base"): (14.42, "T2"),
}

PRIX_CLEARING = None       # prix spot 14h-15h, publie par le prof apres la session 5


def volumes(base, jalon):
    """Volume 2027 a temperature normale, par trimestre, pour un jalon commercial."""
    d = calculer_puissances(calendrier.projeter(base, 2027))
    p = sum(d[f"P_{x}_kW"] / PARAMS[x]["nb_clients"] * CLIENTS[jalon][x] for x in PARAMS)
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
    b_tot = sum(besoin.values())
    print(f"  besoin {b_tot:,.0f} MWh | couvert {e_tot:,.0f} MWh"
          f" -> ratio global {100 * e_tot / b_tot:.1f} %")
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
    for profil, nb in CLIENTS["T3"].items():
        j[f"CM_{profil}"] = coefficient_meteo(
            j[f"grad_{profil}"], j["temperature_normale_lissee_degc"],
            j["temperature_realisee_lissee_degc"])
        base_kw = nb * fud(profil) * j[f"coef_{profil}"]
        j[f"P_{profil}_kW"] = base_kw
        j[f"P_dyn_{profil}_kW"] = base_kw * j[f"CM_{profil}"]
    j = _totaliser(j)

    h = pd.DataFrame({"charge MW": j["P_dyn_totale_kW"].resample("h").mean() / 1000,
                      "charge normale MW": j["P_totale_kW"].resample("h").mean() / 1000})
    h["solaire MW"] = SOLAIRE
    h["couverture MW"] = sum(mw * cv.fenetre(p, n, h.index)
                             for (p, n), (mw, _) in POSITION.items())
    h["position MW"] = h["charge MW"] - h["solaire MW"] - h["couverture MW"]
    h["sens"] = np.where(h["position MW"] > 0, "SHORT (acheter)", "LONG (revendre)")
    return j, h


def ordre_spot(h, heure=HEURE_SPOT):
    """Courbe d'ordre pour une heure : le solaire est offert au marche, le reste est subi."""
    r = h.iloc[heure]
    besoin = r["charge MW"] - r["couverture MW"]       # ce qui manque hors production propre
    print(f"\n{'=' * 78}\nOBJECTIF 2 - ORDRE DAY-AHEAD {heure:02d}h00-{heure + 1:02d}h00"
          f"\n{'=' * 78}")
    print(f"  charge prevue      {r['charge MW']:7.2f} MW")
    print(f"  couverture livree  {r['couverture MW']:7.2f} MW")
    print(f"  production solaire {r['solaire MW']:7.2f} MW")
    print(f"  position ouverte   {r['position MW']:+7.2f} MW  ({r['sens']})")
    print("\n  Courbe d'ordre (le solaire se dispatche contre le prix, pas contre les clients)")
    print(f"    prix < {COUT_MARGINAL_SOLAIRE:.0f} EUR/MWh : on efface le solaire"
          f" -> ACHETER {besoin:6.2f} MWh")
    print(f"    prix >= {COUT_MARGINAL_SOLAIRE:.0f} EUR/MWh : le solaire est vendu"
          f" -> ACHETER {r['position MW']:6.2f} MWh")
    print(f"  Le volume achete est subi : ordre sans limite de prix (price-independent).")
    print(f"  Le solaire porte une limite a {COUT_MARGINAL_SOLAIRE:.0f} EUR/MWh,"
          f" son cout marginal.")

    if PRIX_CLEARING is None:
        print("\n  PRIX_CLEARING non renseigne : hedge success calculable apres publication.")
        return None
    cout = r["position MW"] * PRIX_CLEARING
    cout_nu = (r["charge MW"] - r["solaire MW"]) * PRIX_CLEARING
    print(f"\n  prix de clearing   {PRIX_CLEARING:7.2f} EUR/MWh")
    print(f"  cout de l'heure    {cout:+8.0f} EUR  (sans couverture : {cout_nu:+,.0f} EUR)")
    print(f"  part du besoin couverte par les forwards :"
          f" {100 * r['couverture MW'] / (r['charge MW'] - r['solaire MW']):.1f} %")
    return cout


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
    ordre_spot(h)
    action.to_csv(SORTIES / "t3_reequilibrage.csv", sep=";", decimal=",")
    h.to_csv(SORTIES / "t3_position_20270101.csv", sep=";", decimal=",")
    print("\n-> Exports dans sorties/ : t3_reequilibrage.csv, t3_position_20270101.csv")
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
