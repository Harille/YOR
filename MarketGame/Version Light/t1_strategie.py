"""
T1 — 22/09/2026 : CONSTRUIRE, CHOISIR ET EXECUTER LA STRATEGIE
...............................................................................
Le plan du cours, point par point :
    1. construire la demande
    2. construire des scenarios (historiques, choc fondamental)
    3. construire des strategies
    4. choisir la meilleure (tester les strategies sur les scenarios)
    5. executer la strategie
    6. calculer la demande nette au T1

Ce que ca lit   : donnees/*.csv, et les prix EEX du 22/09/2026 (table EEX)
Ce que ca ecrit : sorties/courbe_de_charge_*.csv (via outils/demande),
                  sorties/comparaison_scenarios.csv,
                  sorties/comparaison_strategies.csv
Duree           : ~11 s
A changer ici   : rien. Tous les parametres du T1 sont dans outils/couverture.py
                  (STRATEGIES, ANNEES, PRIX_VENTE, PLANCHER_RISQUE, FORME...)
Dans le rapport : etapes 1 a 12
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from outils import couverture as cv
from outils import marche
from outils import demande
from outils.demande import SORTIES, construire_base


def main():
    # ==========================================================================
    # T1 - POINT 1 : CONSTRUIRE LA DEMANDE
    # ==========================================================================
    # 1. CONSTRUIRE LA DEMANDE  (premier point du T1)
    #    exporte courbe_de_charge_2025 / _2027 / _2027_T2 dans sorties/
    demande.main()

    # ==========================================================================
    # T1 - POINT 2 : CONSTRUIRE LES SCENARIOS
    # ==========================================================================
    # 2. CONSTRUIRE LES SCENARIOS
    annees = cv.annees_disponibles(cv.ANNEES)
    if len(annees) < 2:
        raise SystemExit("Il faut au moins deux annees pour comparer des scenarios.")
    base = construire_base()

    print(f"\n{'=' * 78}\nETAPE 2 - SCENARIOS ({', '.join(map(str, annees))})\n{'=' * 78}")
    scenarios, brut, b, probabilites = cv.construire_jeu(base, annees)

    # ---- etape 2 bis : pente prix-volume et sa qualite
    groupe = cv.pente_mutualisee(brut)
    print(f"\n{'=' * 78}\nPENTE PRIX-VOLUME b (hiver : mois {cv.MOIS_HIVER})\n{'=' * 78}")
    for an, s in brut.items():
        print(f"  {an} seule   b = {s['b']:+.3f} | r = {s['correlation']:+.3f}"
              f" | r2 = {s['r2']:.3f} | t = {s['t_student']:+.1f} | n = {s['n_jours']}")
    print(f"  MUTUALISEE  b = {groupe['b']:+.3f} | r = {groupe['r']:+.3f}"
          f" | r2 = {groupe['r2']:.3f} | t = {groupe['t']:+.1f} | n = {groupe['n']}")
    print(f"  -> r2 = {groupe['r2']:.0%} : le volume n'explique qu'une part du prix,"
          f" d'ou le test de sensibilite a b ci-dessous.")

    if cv.CHOC_FONDAMENTAL:
        for signe, sens in ((+1, "hausse"), (-1, "baisse")):
            nom = cv.nom_du_choc(signe)
            print(f"  choc a la {sens} : meteo {scenarios[nom]['origine']} + niveau"
                  f" {signe * cv.CHOC_FONDAMENTAL:+.0%} hors meteo,"
                  f" probabilite {cv.PROBA_CHOC:.0%}")
        print(f"  les deux chocs sont symetriques : sans celui a la baisse, le manque a"
              f" gagner de la couverture reste invisible.")

    reference = next(iter(scenarios.values()))["courbe"]
    volumes_q = (reference["charge_normale_MW"]
                 .groupby(reference.index.quarter).sum().to_dict())
    v_annuel = sum(volumes_q.values())

    cv.afficher(cv.tableau(scenarios, probabilites), f"COMPARAISON DES SCENARIOS {marche.ANNEE_CIBLE}")
    print(f"\n  forward Cal-27 Base au T1 (22/09/2026) : {marche.FORWARD_CAL27_T1:.2f} EUR/MWh")
    print(f"  volume de reference (temperature normale) : {v_annuel:,.0f} MWh = 100 %")

    # ---- etape 3 : plausibilite du forward T2 anticipe
    sigma = marche.sigma_t2()
    print(f"\n{'=' * 78}\nETAPE 3 - FORWARD T2 ANTICIPE (methode alpha)\n{'=' * 78}")
    print(f"  bande de plausibilite CRE : {marche.FORWARD_CAL27_T1:.2f} +/- {sigma:.2f}"
          f" soit [{marche.FORWARD_CAL27_T1 - sigma:.2f} ; {marche.FORWARD_CAL27_T1 + sigma:.2f}]"
          f" a 1 sigma ({marche.VOLATILITE_CRE:.0%} annuel sur {marche.JOURS_T1_T2} jours)")
    lignes = []
    for an, s in scenarios.items():
        ligne = {"annee": an, "Level": s["niveau"]}
        for a in (0.2, cv.ALPHA_T2, 0.6):
            ligne[f"alpha {a}"] = marche.forward_t2_anticipe(s["niveau"], a)
        ligne["alpha requis / reel"] = ((marche.FORWARD_CAL27_T2 - marche.FORWARD_CAL27_T1)
                                        / (s["niveau"] - marche.FORWARD_CAL27_T1))
        lignes.append(ligne)
    cv.afficher(pd.DataFrame(lignes).set_index("annee"))
    print(f"  forward reel observe au T2 : {marche.FORWARD_CAL27_T2:.2f} EUR/MWh")

    # ==========================================================================
    # T1 - POINT 3 : CONSTRUIRE DES STRATEGIES
    # ==========================================================================
    # ---- etape 4 : mix de produits
    print(f"\n{'=' * 78}\nETAPE 4 - MIX DE PRODUITS, A COUVERTURE EGALE\n{'=' * 78}")
    h1_ref = cv.STRATEGIES["Notre strategie 70/20/10"][0]
    index = reference.index
    for forme in ("cal", "trimestres", "trimestres+peak"):
        mix = cv.construire_mix(h1_ref, volumes_q, index, forme)
        energie = sum(mw * cv.heures_livrees(p, n, index) for (p, n), mw in mix.items())
        cout = cv.cout_mix(mix, index, "T1")
        print(f"  {forme:<18} {len(mix)} produits | {energie:>9,.0f} MWh"
              f" ({energie / v_annuel:>5.1%} du volume) | {cout / 1e6:>6.2f} MEUR"
              f" | {cout / energie:>6.2f} EUR/MWh")
    print(f"\n  detail du mix retenu ({cv.FORME}) pour {h1_ref:.0%} achetes au T1 :")
    cv.afficher(cv.decrire_mix(cv.construire_mix(h1_ref, volumes_q, index), index, "T1"))

    # ==========================================================================
    # T1 - POINTS 4 ET 5 : CHOISIR LA MEILLEURE, PUIS L'EXECUTER
    # ==========================================================================
    # ---- etape 5 : marges, choix, couts de la protection
    strat = cv.evaluer_strategies(scenarios, volumes_q, probabilites)
    cv.afficher(strat, f"ETAPE 5 - MARGE PAR STRATEGIE (EUR/MWh, mix {cv.FORME})")
    print(f"  prix de vente {cv.PRIX_VENTE:.0f} | marge cible {cv.MARGE_CIBLE:.0f}"
          f" | plancher {cv.PLANCHER_RISQUE:.0f} | probabilites "
          + ", ".join(f"{an} {probabilites[an]:.0%}" for an in scenarios))

    choix = cv.choisir(strat)
    if choix:
        print(f"  -> retenue : {choix} (esperance {strat.loc[choix, 'esperance']:.2f},"
              f" pire cas {strat.loc[choix, 'pire cas']:.2f})")
    else:
        print(f"  -> AUCUNE strategie ne tient le plancher de {cv.PLANCHER_RISQUE:.0f} EUR/MWh :"
              f" le portefeuille est structurellement trop cher a {cv.PRIX_VENTE:.0f} EUR/MWh.")
        repli = strat["pire cas"].idxmax()
        print(f"  -> regle de repli : le MEILLEUR PIRE CAS, soit {repli}"
              f" (pire cas {strat.loc[repli, 'pire cas']:+.2f},"
              f" esperance {strat.loc[repli, 'esperance']:.2f} EUR/MWh).")
        print(f"     C'est cette strategie qui est reprise au T2"
              f" (STRATEGIE_T1 en tete de t2_decision.py).")

    ref = strat["couv. prevue %"].idxmin()
    prot = pd.DataFrame({
        "esperance cedee": strat.loc[ref, "esperance"] - strat["esperance"],
        "pire cas gagne": strat["pire cas"] - strat.loc[ref, "pire cas"]})
    prot["prix de la protection"] = (prot["esperance cedee"]
                                     / prot["pire cas gagne"].replace(0, np.nan))
    cv.afficher(prot, f"COUT DE LA PROTECTION (reference : {ref})")

    print(f"\n{'=' * 78}\nSENSIBILITE DE LA DECISION\n{'=' * 78}")
    best = strat["pire cas"].idxmax()
    print(f"  meilleure protection possible : {best}"
          f" (pire cas {strat.loc[best, 'pire cas']:.2f} EUR/MWh)")
    print("  plancher du Conseil :")
    for p in sorted({-2.5, 0.0, 2.5, 5.0, cv.PLANCHER_RISQUE, 7.5, 10.0}):
        c = cv.choisir(strat, p)
        print(f"    {p:>5.1f} EUR/MWh -> {c or 'aucune strategie admissible'}")
    print("  pente b :")
    for nom, valeur in [("minimum annuel", min(s["b"] for s in brut.values())),
                        ("mutualisee", b),
                        ("maximum annuel", max(s["b"] for s in brut.values()))]:
        sc_b = {an: cv.reajuster(s, valeur, marche.FORWARD_CAL27_T1 * s["multiplicateur_forward"])
                for an, s in scenarios.items()}
        t = cv.evaluer_strategies(sc_b, volumes_q, probabilites)
        print(f"    b = {valeur:+.3f} ({nom:<15}) -> meilleure esperance :"
              f" {t['esperance'].idxmax()} | admissible : {cv.choisir(t) or 'aucune'}")
    print("  alpha :")
    for a in (0.2, cv.ALPHA_T2, 0.6):
        t = cv.evaluer_strategies(scenarios, volumes_q, probabilites, alpha=a)
        print(f"    alpha = {a:.1f} -> meilleure esperance : {t['esperance'].idxmax()}"
              f" | admissible : {cv.choisir(t) or 'aucune'}")
    print("  mix de produits :")
    for forme in ("cal", "trimestres", "trimestres+peak"):
        t = cv.evaluer_strategies(scenarios, volumes_q, probabilites, forme=forme)
        print(f"    {forme:<18} -> meilleure esperance : {t['esperance'].idxmax()}"
              f" ({t['esperance'].max():.2f}) | admissible : {cv.choisir(t) or 'aucune'}")

    cv.tableau(scenarios, probabilites).to_csv(SORTIES / "comparaison_scenarios.csv",
                                            sep=";", decimal=",")
    strat.to_csv(SORTIES / "comparaison_strategies.csv", sep=";", decimal=",")
    print("\n-> Exports dans sorties/ : comparaison_scenarios.csv, comparaison_strategies.csv")
    return strat, scenarios, volumes_q


def tracer(scenarios):
    fig, axes = plt.subplots(3, 1, figsize=(14, 11))
    for an, s in scenarios.items():
        prix_j = s["courbe"]["spot_EUR_MWh"].resample("D").mean()
        charge_j = s["courbe"]["charge_MW"].resample("D").mean()
        axes[0].plot(prix_j.index, prix_j, lw=0.8, label=f"scenario {an}")
        axes[1].plot(charge_j.index, charge_j, lw=0.8, label=f"scenario {an}")
    axes[0].set_ylabel("EUR/MWh"); axes[0].set_title(f"Prix spot {marche.ANNEE_CIBLE}"); axes[0].legend()
    axes[1].set_ylabel("MW"); axes[1].set_title("Charge journaliere moyenne"); axes[1].legend()

    couts = [s["courbe"]["cout_EUR"].sum() / 1e6 for s in scenarios.values()]
    axes[2].bar([str(a) for a in scenarios], couts, color="tab:blue")
    for i, v in enumerate(couts):
        axes[2].text(i, v, f"{v:,.1f}", ha="center", va="bottom")
    axes[2].set_ylabel("MEUR"); axes[2].set_title("Cout total au spot, par scenario")
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout(); plt.show()


if __name__ == "__main__":
    table, scen, vol_q = main()
    tracer(scen)
