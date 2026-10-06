"""
T2 — 01/12/2026 : ACTUALISER, REVISER, DECIDER, EXECUTER
...............................................................................
Le plan du cours, point par point :
    1. actualiser toutes les donnees avec les infos du T2
       (nombre de consommateurs, meteo, prix releves le 01/12/2026)
    2. calculer la demande nette avec le hedging actualise
    3. (facultatif) faire evoluer la strategie
    4. executer la strategie

Les achats du T1 sont FIGES : on ne les rejoue pas, on les valorise au prix du
jour (mark-to-market) et on decide seulement ce qu'on achete EN PLUS.

Ce que ca lit   : donnees/*.csv, et les prix EEX du 01/12/2026 (table EEX)
Ce que ca ecrit : sorties/decision_t2.csv,
                  sorties/position_ouverte_20270101.csv
Duree           : ~5 s
A changer ici   : STRATEGIE_T1 (la strategie retenue au T1), JOUR_SPOT,
                  OPTIONS_T2 (les taux de couverture testes)
Dans le rapport : etapes 13 et 14
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from outils import calendrier
from outils import couverture as cv
from outils import marche
from outils.demande import SORTIES, construire_base

JOUR_SPOT = "2027-01-01"          # vendredi ferie
STRATEGIE_T1 = "Notre strategie 70/20/10"
OPTIONS_T2 = {                    # cible de couverture TOTALE sur le volume revise
    "ne rien acheter de plus": None,
    "completer a 85 %": 0.85,
    "completer a 90 % (plan du T1)": 0.90,
    "completer a 100 %": 1.00,
}
FORMES_T2 = ("cal", "trimestres")


def probabilites_revisees(scenarios, priors, alpha=None, forward_observe=None):
    """4.2 - mise a jour bayesienne par la vraisemblance du prix observe au T2.

    posterieure ~ anterieure x exp(-0.5 x ((forward anticipe - forward observe) / sigma)^2)
    sigma etant deduit de la volatilite annuelle CRE sur l'horizon T1 -> T2.
    Regle unique, appliquee identiquement a tous les scenarios.
    """
    alpha = cv.ALPHA_T2 if alpha is None else alpha
    observe = marche.FORWARD_CAL27_T2 if forward_observe is None else forward_observe
    sigma = marche.sigma_t2()
    poids = {an: priors[an] * float(np.exp(
        -0.5 * ((marche.forward_t2_anticipe(s["niveau"], alpha) - observe) / sigma) ** 2))
        for an, s in scenarios.items()}
    total = sum(poids.values())
    return {an: p / total for an, p in poids.items()}


def mark_to_market(mix, index):
    """Valeur de la position T1 aux prix du 01/12/2026."""
    lignes = []
    for (p, n), mw in sorted(mix.items()):
        h = cv.heures_livrees(p, n, index)
        t1, t2 = marche.prix_eex(p, n, "T1"), marche.prix_eex(p, n, "T2")
        lignes.append({"produit": p, "nature": n, "MW": mw, "MWh": mw * h,
                       "prix T1": t1, "prix T2": t2, "ecart": t2 - t1,
                       "MtM MEUR": mw * h * (t2 - t1) / 1e6})
    tab = pd.DataFrame(lignes)
    return tab, tab["MtM MEUR"].sum()


def marge_t2(scenario, mix_t1, mix_t2, prix_vente=cv.PRIX_VENTE):
    """4.4 - T1 fige, T2 aux prix reels, residuel au spot du scenario, volume revise."""
    courbe = scenario["courbe"]
    index = courbe.index
    charge = courbe["charge_T2_MW"]
    livre = cv.livraison(mix_t1, index) + cv.livraison(mix_t2, index)
    residuel = charge - livre

    cout = (cv.cout_mix(mix_t1, index, "T1") + cv.cout_mix(mix_t2, index, "T2")
            + float((residuel * courbe["spot_EUR_MWh"]).sum()))
    volume = scenario["energie_scenario_T2"]
    marge_eur = prix_vente * volume - cout
    return {"cout_total": cout, "marge_EUR": marge_eur, "marge_EUR_MWh": marge_eur / volume,
            "couverture_%": 100 * livre.sum() / scenario["energie_normale_T2"],
            "achat_spot_MWh": float(residuel[residuel > 0].sum()),
            "revente_spot_MWh": float(-residuel[residuel < 0].sum())}


def main():
    base = construire_base()
    annees = cv.annees_disponibles(cv.ANNEES)

    print(f"\n{'=' * 78}\nSCENARIOS (rappel du T1)\n{'=' * 78}")
    # scen_t1 : niveaux tels qu'ils etaient au T1, ancres sur 83.31
    scen_t1, brut, b, priors = cv.construire_jeu(base, annees)

    index = next(iter(scen_t1.values()))["courbe"].index
    volumes_q_t1 = (next(iter(scen_t1.values()))["courbe"]["charge_normale_MW"]
                    .groupby(np.asarray(index.quarter)).sum().to_dict())
    v_ref_t1 = sum(volumes_q_t1.values())
    volumes_q_t2 = (next(iter(scen_t1.values()))["courbe"]["charge_normale_T2_MW"]
                    .groupby(np.asarray(index.quarter)).sum().to_dict())
    v_ref_t2 = sum(volumes_q_t2.values())

    # ==========================================================================
    # T2 - POINT 1 : ACTUALISER LES DONNEES
    # prix releves le 01/12, probabilites revisees, nouveau nombre de clients
    # ==========================================================================
    # ------------------------------------------------- 4.1 anticipation vs realite
    print(f"\n{'=' * 78}\n4.1 - ANTICIPATION CONTRE REALITE\n{'=' * 78}")
    sigma = marche.sigma_t2()
    lignes = []
    for an, s in scen_t1.items():
        f = marche.forward_t2_anticipe(s["niveau"], cv.ALPHA_T2)
        lignes.append({"annee": an, "Level T1": s["niveau"], "fwd T2 anticipe": f,
                       "fwd T2 reel": marche.FORWARD_CAL27_T2, "erreur": marche.FORWARD_CAL27_T2 - f,
                       "erreur / sigma": (marche.FORWARD_CAL27_T2 - f) / sigma,
                       "alpha requis": ((marche.FORWARD_CAL27_T2 - marche.FORWARD_CAL27_T1)
                                        / (s["niveau"] - marche.FORWARD_CAL27_T1))})
    cv.afficher(pd.DataFrame(lignes).set_index("annee"))
    anticipes = [marche.forward_t2_anticipe(s["niveau"], cv.ALPHA_T2) for s in scen_t1.values()]
    dedans = min(anticipes) <= marche.FORWARD_CAL27_T2 <= max(anticipes)
    print(f"  forward T1 {marche.FORWARD_CAL27_T1:.2f} -> T2 reel {marche.FORWARD_CAL27_T2:.2f}"
          f" ({marche.FORWARD_CAL27_T2 / marche.FORWARD_CAL27_T1 - 1:+.1%}), sigma CRE = {sigma:.2f}")
    print(f"  le prix observe est {'DANS' if dedans else 'HORS'} la fourchette anticipee"
          f" [{min(anticipes):.2f} ; {max(anticipes):.2f}]")
    print(f"  alpha retenu {cv.ALPHA_T2:.2f} ; aucun alpha de [0 ; 1] n'atteint 73.70"
          f" -> la baisse n'est pas d'origine meteo (gaz, CO2, nucleaire, demande).")

    # ------------------------------------------------- 4.2 probabilites revisees
    probas = probabilites_revisees(scen_t1, priors)
    print(f"\n{'=' * 78}\n4.2 - PROBABILITES REVISEES\n{'=' * 78}")
    for an in scen_t1:
        print(f"  {an:<10} : {priors[an]:.1%} au T1 -> {probas[an]:.1%} au T2"
              f"  (fwd anticipe {marche.forward_t2_anticipe(scen_t1[an]['niveau'], cv.ALPHA_T2):.2f}"
              f" vs {marche.FORWARD_CAL27_T2:.2f} observe)")
    print("  regle : anterieure x vraisemblance gaussienne du prix observe, ecart-type ="
          " volatilite CRE sur 70 jours. Meme regle pour tous les scenarios.")

    # ==========================================================================
    # T2 - POINT 2 : LA DEMANDE NETTE AVEC LE HEDGING ACTUALISE
    # ==========================================================================
    # ------------------------------------------------- 4.3 volume et ratio atteint
    mix_t1 = cv.construire_mix(cv.STRATEGIES[STRATEGIE_T1][0], volumes_q_t1, index)
    energie_t1 = sum(mw * cv.heures_livrees(p, n, index) for (p, n), mw in mix_t1.items())
    ratio_t1 = energie_t1 / v_ref_t2
    print(f"\n{'=' * 78}\n4.3 - VOLUME ET RATIO DE COUVERTURE\n{'=' * 78}")
    print(f"  prevision T1 : {v_ref_t1:,.0f} MWh  ->  prevision T2 : {v_ref_t2:,.0f} MWh"
          f"  ({v_ref_t2 / v_ref_t1 - 1:+.2%})")
    print(f"  achats du T1 : {energie_t1:,.0f} MWh"
          f" = {100 * energie_t1 / v_ref_t1:.1f} % de l'ancienne prevision"
          f" -> {100 * ratio_t1:.1f} % de la nouvelle")
    plan = sum(cv.STRATEGIES[STRATEGIE_T1])
    print(f"  portefeuille {'RETRECI' if v_ref_t2 < v_ref_t1 else 'ELARGI'} :"
          f" nous sommes SUR-couvert de {100 * (ratio_t1 - cv.STRATEGIES[STRATEGIE_T1][0]):+.1f}"
          f" point(s) par rapport au plan du T1")
    print(f"  marge de manoeuvre restante jusqu'a 100 % : {100 * (1 - ratio_t1):.1f} %"
          f" soit {v_ref_t2 - energie_t1:,.0f} MWh (le plan prevoyait {100 * (plan - 0.70):.0f} %)")

    tab_mtm, mtm = mark_to_market(mix_t1, index)
    cv.afficher(tab_mtm, "MARK-TO-MARKET DE LA POSITION T1, AUX PRIX DU 01/12/2026")
    print(f"  total : {mtm:+,.2f} MEUR soit {1e6 * mtm / energie_t1:+.2f} EUR/MWh couvert")

    # ==========================================================================
    # T2 - POINTS 3 ET 4 : FAIRE EVOLUER LA STRATEGIE, PUIS L'EXECUTER
    # ==========================================================================
    # ------------------------------------------------- 4.4 decision du T2
    scen_t2 = {an: cv.reajuster(s, b, marche.FORWARD_CAL27_T2 * s["multiplicateur_forward"])
               for an, s in scen_t1.items()}
    lignes = {}
    mixes = {}
    for libelle, cible in OPTIONS_T2.items():
        formes = (None,) if cible is None else FORMES_T2
        for forme in formes:
            part = 0.0 if cible is None else max(cible - ratio_t1, 0.0)
            mix_t2 = {} if part <= 0 else cv.construire_mix(part, volumes_q_t2, index, forme)
            nom = libelle if cible is None else f"{libelle} - {forme}"
            det = {an: marge_t2(s, mix_t1, mix_t2) for an, s in scen_t2.items()}
            marges = {an: d["marge_EUR_MWh"] for an, d in det.items()}
            ligne = {"achat T2 %": 100 * part,
                     "couverture %": max(d["couverture_%"] for d in det.values())}
            ligne.update({f"marge {an}": m for an, m in marges.items()})
            ligne["esperance"] = sum(probas[an] * m for an, m in marges.items())
            ligne["pire cas"] = min(marges.values())
            ligne["admissible"] = ligne["pire cas"] >= cv.PLANCHER_RISQUE
            lignes[nom] = ligne
            mixes[nom] = mix_t2
    cols = ["achat T2 %", "couverture %"] + [f"marge {an}" for an in scen_t2] + \
           ["esperance", "pire cas", "admissible"]
    options = pd.DataFrame(lignes).T[cols]
    cv.afficher(options, "4.4 - DECISION DU T2 (achats du T1 figes, prix reels du 01/12/2026)")
    print(f"  prix de vente {cv.PRIX_VENTE:.0f} | plancher {cv.PLANCHER_RISQUE:.0f}"
          f" | probabilites revisees | volume {v_ref_t2:,.0f} MWh")

    admissibles = options[options["pire cas"] >= cv.PLANCHER_RISQUE]
    choix = (admissibles["esperance"].idxmax() if len(admissibles)
             else options["pire cas"].idxmax())
    print(f"  -> retenu : {choix} (esperance {options.loc[choix, 'esperance']:.2f},"
          f" pire cas {options.loc[choix, 'pire cas']:.2f} EUR/MWh,"
          f" couverture {options.loc[choix, 'couverture %']:.1f} %)")
    if not len(admissibles):
        print(f"     ATTENTION : aucune option ne tient le plancher,"
              f" on retient le moins mauvais pire cas.")

    mix_final = dict(mix_t1)
    for cle, mw in mixes[choix].items():
        mix_final[cle] = mix_final.get(cle, 0.0) + mw
    if mixes[choix]:
        cv.afficher(cv.decrire_mix(mixes[choix], index, "T2"), "PRODUITS ACHETES AU T2")

    # ==========================================================================
    # T2 - LA DEMANDE NETTE QUI RESTE, HEURE PAR HEURE
    # ==========================================================================
    # ------------------------------------------------- 5. position ouverte 01/01/2027
    jour = index[np.asarray(index.date) == pd.Timestamp(JOUR_SPOT).date()]
    livre = cv.livraison(mix_final, jour)
    pos = pd.DataFrame({"charge normale MW": next(iter(scen_t2.values()))["courbe"]
                        .loc[jour, "charge_normale_T2_MW"]})
    for an, s in scen_t2.items():
        pos[f"charge {an} MW"] = s["courbe"].loc[jour, "charge_T2_MW"]
    pos["couverture MW"] = livre
    pos["position normale MW"] = pos["charge normale MW"] - pos["couverture MW"]
    for an in scen_t2:
        pos[f"position {an} MW"] = pos[f"charge {an} MW"] - pos["couverture MW"]
    pos["sens"] = np.where(pos["position normale MW"] > 0, "SHORT (acheter)", "LONG (revendre)")
    pos.index = [f"{h:%H:%M}-{h + pd.Timedelta(hours=1):%H:%M}" for h in pos.index]

    feries = calendrier.jours_feries(pd.Timestamp(JOUR_SPOT).year)
    est_ferie = pd.Timestamp(JOUR_SPOT).date() in feries
    cv.afficher(pos.round(2), f"5 - POSITION OUVERTE DU {pd.Timestamp(JOUR_SPOT):%d/%m/%Y}"
                              f" ({pd.Timestamp(JOUR_SPOT):%A}"
                              f"{', JOUR FERIE' if est_ferie else ''})")
    peak = [(p, n) for (p, n) in mix_final if n == "Peak"]
    print(f"  profil utilise : type FERIE (et non un vendredi ordinaire)")
    print(f"  produits Peak detenus : {len(peak)}"
          f" -> {'puissance recue 08h-20h un jour ferie, a revendre' if peak else 'aucun'}")
    print(f"  a acheter au day-ahead : {pos['position normale MW'].clip(lower=0).sum():,.1f} MWh"
          f" | a revendre : {-pos['position normale MW'].clip(upper=0).sum():,.1f} MWh")

    pos.to_csv(SORTIES / "position_ouverte_20270101.csv", sep=";", decimal=",")
    options.to_csv(SORTIES / "decision_t2.csv", sep=";", decimal=",")
    print("\n-> Exports dans sorties/ : decision_t2.csv, position_ouverte_20270101.csv")
    return options, pos, mix_final


def tracer(pos):
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    x = range(len(pos))
    axes[0].plot(x, pos["charge normale MW"], lw=2, color="tab:green", label="charge (T normale)")
    for col in [c for c in pos.columns if c.startswith("charge 2")]:
        axes[0].plot(x, pos[col], lw=0.9, ls="--", label=col)
    axes[0].step(x, pos["couverture MW"], where="mid", lw=2, color="tab:red",
                 label="couverture livree")
    axes[0].set_ylabel("MW"); axes[0].legend(fontsize=8); axes[0].set_title(
        f"Charge et couverture, {JOUR_SPOT}")

    val = pos["position normale MW"]
    axes[1].bar(x, val, color=np.where(val > 0, "tab:red", "tab:blue"))
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].set_ylabel("MW"); axes[1].set_xlabel("heure")
    axes[1].set_title("Position ouverte : rouge = short (acheter), bleu = long (revendre)")
    for ax in axes:
        ax.set_xticks(list(x)[::2]); ax.set_xticklabels(list(pos.index)[::2], rotation=90, fontsize=7)
        ax.grid(alpha=0.3)
    fig.tight_layout(); plt.show()


if __name__ == "__main__":
    opt, position, mix = main()
    tracer(position)
