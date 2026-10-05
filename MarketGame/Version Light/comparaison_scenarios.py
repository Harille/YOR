import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import scenarios as sc
from Modelisation_Conso import SORTIES, construire_base, masque_peak

ANNEES = [2021, 2023, 2024]
MOIS_HIVER = [1, 2, 3, 11, 12]

PRIX_VENTE = 95.0          # EUR/MWh, impose par le Conseil
MARGE_CIBLE = 10.0         # EUR/MWh
PLANCHER_RISQUE = 5.0      # EUR/MWh, pire cas minimum
ALPHA_T2 = 0.50            # part du scenario deja dans les prix au 01/12/2026
FORME = "trimestres"       # "cal" | "trimestres" | "trimestres+peak"

# Scenario de choc de NIVEAU, hors meteo (gaz, CO2, disponibilite nucleaire, demande).
# Indispensable : sans lui, le Level vaut toujours forward x (1 - prime), donc le spot
# est espere moins cher que le forward et le modele conclut mecaniquement "ne jamais se
# couvrir". +20 % = un ecart-type, c'est la volatilite annuelle estimee par la CRE.
CHOC_FONDAMENTAL = 0.20    # 0.0 pour desactiver le scenario de choc
PROBA_CHOC = 0.15          # probabilite du choc (queue haute a 1 sigma)

STRATEGIES = {             # (part achetee a T1, part planifiee pour T2) - le reste au SPOT
    "Notre strategie 70/20/10": (0.70, 0.20),
    "Variante 50/25/25":        (0.50, 0.25),
    "A - front loaded":         (0.50, 0.40),
    "B - peu couverte":         (0.40, 0.40),
    "C - totalement couverte":  (0.40, 0.60),
    "D - back loaded":          (0.40, 0.50),
}

MOIS_EEX = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6}


# --------------------------------------------------------------- produits EEX
def fenetre(produit, nature, index):
    """Masque des pas de temps ou le produit livre effectivement."""
    nom = produit.split("-")[0]
    if nom == "Cal":
        m = np.ones(len(index), dtype=bool)
    elif nom[0] == "Q":
        m = np.asarray(index.quarter) == int(nom[1:])
    else:
        m = np.asarray(index.month) == MOIS_EEX[nom]
    if nature == "Peak":                       # lun-ven 08h-20h, jours feries inclus
        m = m & np.asarray(masque_peak(index))
    return pd.Series(m, index=index)


def heures_livrees(produit, nature, index):
    return float(fenetre(produit, nature, index).sum())


def livraison(mix, index):
    """mix = {(produit, nature): MW} -> puissance livree a chaque heure."""
    out = pd.Series(0.0, index=index)
    for (produit, nature), mw in mix.items():
        out += mw * fenetre(produit, nature, index)
    return out


def cout_mix(mix, index, jalon="T1"):
    return sum(mw * sc.prix_eex(p, n, jalon) * heures_livrees(p, n, index)
               for (p, n), mw in mix.items())


def construire_mix(part, volumes_q, index, forme=None, ratio_peak=1.32):
    """Convertit une part de volume en MW par produit EEX (etape 4 du cours)."""
    forme = FORME if forme is None else forme
    if forme == "cal":
        return {("Cal-27", "Base"): part * sum(volumes_q.values())
                                    / heures_livrees("Cal-27", "Base", index)}
    mix = {}
    for q, v in volumes_q.items():
        produit = f"Q{q}-27"
        h_base = heures_livrees(produit, "Base", index)
        if forme == "trimestres+peak":
            # Base B + Peak P tels que (B+P)/B = ratio de forme de la charge
            h_peak = heures_livrees(produit, "Peak", index)
            b = part * v / (h_base + (ratio_peak - 1) * h_peak)
            mix[(produit, "Base")] = b
            mix[(produit, "Peak")] = b * (ratio_peak - 1)
        else:
            mix[(produit, "Base")] = part * v / h_base
    return mix


def decrire_mix(mix, index, jalon="T1"):
    lignes = [{"produit": p, "nature": n, "MW": mw,
               "heures": heures_livrees(p, n, index),
               "MWh": mw * heures_livrees(p, n, index),
               f"prix {jalon}": sc.prix_eex(p, n, jalon),
               "cout MEUR": mw * sc.prix_eex(p, n, jalon) * heures_livrees(p, n, index) / 1e6}
              for (p, n), mw in sorted(mix.items())]
    return pd.DataFrame(lignes)


# ------------------------------------------------------------------ scenarios
def annees_disponibles(annees):
    ok = []
    for an in annees:
        try:
            sc._fichier("temperature", an)
            sc._fichier("prix", an)
            ok.append(an)
        except FileNotFoundError:
            print(f"  [ignore] {an} : temperature ou prix manquant")
    return ok


def pente_mutualisee(scenarios):
    paquet = pd.concat([s["anomalies"][s["anomalies"].index.month.isin(MOIS_HIVER)]
                        for s in scenarios.values()])
    return sc.pente_prix_volume(paquet)


def construire_jeu(base, annees, forward=None, bavard=True):
    """Les scenarios meteo, la pente mutualisee, le scenario de choc et les probabilites."""
    forward = sc.FORWARD_CAL27_T1 if forward is None else forward
    brut = {}
    for an in annees:
        if bavard:
            print(f"\n--- scenario {an} ---")
        brut[an] = sc.construire_scenario(an, base, bavard=bavard)
    b = pente_mutualisee(brut)["b"]

    scenarios = {an: reajuster(s, b, forward) for an, s in brut.items()}
    if CHOC_FONDAMENTAL:
        froid = min(brut, key=lambda a: brut[a]["temperature_moyenne"])
        nom = f"choc {CHOC_FONDAMENTAL:+.0%}"
        scenarios[nom] = reajuster(brut[froid], b, forward * (1 + CHOC_FONDAMENTAL))
        scenarios[nom]["multiplicateur_forward"] = 1 + CHOC_FONDAMENTAL
        scenarios[nom]["origine"] = froid
        reste = (1 - PROBA_CHOC) / len(brut)
        probabilites = {an: reste for an in brut} | {nom: PROBA_CHOC}
    else:
        probabilites = {an: 1 / len(brut) for an in brut}
    return scenarios, brut, b, probabilites


def reajuster(scenario, b, forward):
    """Re-ancre le Level sur un forward et une pente donnes, sans refaire la projection."""
    niveau = forward * (1 - sc.PRIME_DE_RISQUE) * (1 + b * scenario["anomalie_volume"])
    courbe = scenario["courbe"].copy()
    courbe["spot_EUR_MWh"] *= niveau / scenario["niveau"]
    courbe["cout_EUR"] = courbe["charge_MW"] * courbe["spot_EUR_MWh"]

    out = dict(scenario)
    out.setdefault("multiplicateur_forward", 1.0)
    out.update({"b_retenu": b, "niveau": niveau, "courbe": courbe,
                "prix_moyen": courbe["spot_EUR_MWh"].mean(),
                "prix_pondere": courbe["cout_EUR"].sum() / courbe["charge_MW"].sum(),
                "cout_total": courbe["cout_EUR"].sum()})
    out["surcout_prix_volume"] = out["prix_pondere"] - out["prix_moyen"]
    return out


# --------------------------------------------------------------------- marges
def marge(scenario, h1, h2, volumes_q, alpha=None, forme=None, prix_vente=PRIX_VENTE):
    """Marge d'une strategie : vente - couverture T1 - tranche T2 - residuel au spot."""
    alpha = ALPHA_T2 if alpha is None else alpha
    courbe = scenario["courbe"]
    index = courbe.index
    v_ref = scenario["energie_normale"]          # le 100 % des ratios
    forward_t2 = sc.forward_t2_anticipe(scenario["niveau"], alpha)

    mix_t1 = construire_mix(h1, volumes_q, index, forme)
    livre_t1 = livraison(mix_t1, index)
    mw_t2 = h2 * v_ref / len(index)              # tranche T2 : ruban, prix encore inconnu
    residuel = courbe["charge_MW"] - livre_t1 - mw_t2

    cout = (cout_mix(mix_t1, index, "T1") + h2 * v_ref * forward_t2
            + float((residuel * courbe["spot_EUR_MWh"]).sum()))
    volume_vendu = scenario["energie_scenario"]
    marge_eur = prix_vente * volume_vendu - cout
    return {"forward_T2": forward_t2, "cout_total": cout, "marge_EUR": marge_eur,
            "marge_EUR_MWh": marge_eur / volume_vendu,
            "couv_prevue_%": 100 * (livre_t1.sum() + mw_t2 * len(index)) / v_ref,
            "couv_realisee_%": 100 * (livre_t1.sum() + mw_t2 * len(index)) / volume_vendu,
            "achat_spot_MWh": float(residuel[residuel > 0].sum()),
            "revente_spot_MWh": float(-residuel[residuel < 0].sum())}


def evaluer_strategies(scenarios, volumes_q, probabilites=None, alpha=None, forme=None):
    probabilites = probabilites or {an: 1 / len(scenarios) for an in scenarios}
    lignes = {}
    for nom, (h1, h2) in STRATEGIES.items():
        det = {an: marge(s, h1, h2, volumes_q, alpha, forme) for an, s in scenarios.items()}
        marges = {an: d["marge_EUR_MWh"] for an, d in det.items()}
        ligne = {"T1 %": 100 * h1, "T2 %": 100 * h2,
                 "couv. prevue %": max(d["couv_prevue_%"] for d in det.values()),
                 "couv. max realisee %": max(d["couv_realisee_%"] for d in det.values())}
        ligne.update({f"marge {an}": m for an, m in marges.items()})
        ligne["esperance"] = sum(probabilites[an] * m for an, m in marges.items())
        ligne["pire cas"] = min(marges.values())
        ligne["admissible"] = ligne["pire cas"] >= PLANCHER_RISQUE
        lignes[nom] = ligne
    cols = ["T1 %", "T2 %", "couv. prevue %", "couv. max realisee %"] + \
           [f"marge {an}" for an in scenarios] + \
           ["esperance", "pire cas", "admissible"]
    return pd.DataFrame(lignes).T[cols]


def choisir(strat, plancher=None):
    plancher = PLANCHER_RISQUE if plancher is None else plancher
    ok = strat[strat["pire cas"] >= plancher]
    return ok["esperance"].idxmax() if len(ok) else None


def tableau(scenarios, probabilites):
    lignes = []
    for an, s in scenarios.items():
        c = s["courbe"]
        trim = c["cout_EUR"].groupby(c.index.quarter).sum() / 1e6
        lignes.append({"annee": an, "probabilite": probabilites[an],
                       "T moyenne (C)": s["temperature_moyenne"],
                       "prix hist (EUR/MWh)": s["prix_historique_moyen"],
                       "volume (MWh)": s["energie_scenario"],
                       "anomalie volume %": 100 * s["anomalie_volume"],
                       "pointe (MW)": s["pointe_MW"], "Level (EUR/MWh)": s["niveau"],
                       "fwd T2 anticipe": sc.forward_t2_anticipe(s["niveau"], ALPHA_T2),
                       "prix pondere (EUR/MWh)": s["prix_pondere"],
                       "surcout (EUR/MWh)": s["surcout_prix_volume"],
                       "cout total (MEUR)": s["cout_total"] / 1e6,
                       "dont Q4 (MEUR)": trim.get(4, np.nan)})
    return pd.DataFrame(lignes).set_index("annee")


def afficher(df, titre=None):
    if titre:
        print(f"\n{'=' * 78}\n{titre}\n{'=' * 78}")
    with pd.option_context("display.width", 220, "display.max_columns", 30,
                           "display.float_format", lambda x: f"{x:,.2f}"):
        print(df.to_string())


def main():
    annees = annees_disponibles(ANNEES)
    if len(annees) < 2:
        raise SystemExit("Il faut au moins deux annees pour comparer des scenarios.")
    base = construire_base()

    print(f"\n{'=' * 78}\nETAPE 2 - SCENARIOS ({', '.join(map(str, annees))})\n{'=' * 78}")
    scenarios, brut, b, probabilites = construire_jeu(base, annees)

    # ---- etape 2 bis : pente prix-volume et sa qualite
    groupe = pente_mutualisee(brut)
    print(f"\n{'=' * 78}\nPENTE PRIX-VOLUME b (hiver : mois {MOIS_HIVER})\n{'=' * 78}")
    for an, s in brut.items():
        print(f"  {an} seule   b = {s['b']:+.3f} | r = {s['correlation']:+.3f}"
              f" | r2 = {s['r2']:.3f} | t = {s['t_student']:+.1f} | n = {s['n_jours']}")
    print(f"  MUTUALISEE  b = {groupe['b']:+.3f} | r = {groupe['r']:+.3f}"
          f" | r2 = {groupe['r2']:.3f} | t = {groupe['t']:+.1f} | n = {groupe['n']}")
    print(f"  -> r2 = {groupe['r2']:.0%} : le volume n'explique qu'une part du prix,"
          f" d'ou le test de sensibilite a b ci-dessous.")

    if CHOC_FONDAMENTAL:
        nom = f"choc {CHOC_FONDAMENTAL:+.0%}"
        print(f"  scenario de choc : meteo {scenarios[nom]['origine']} + niveau"
              f" {CHOC_FONDAMENTAL:+.0%} hors meteo, probabilite {PROBA_CHOC:.0%}")

    reference = next(iter(scenarios.values()))["courbe"]
    volumes_q = (reference["charge_normale_MW"]
                 .groupby(reference.index.quarter).sum().to_dict())
    v_annuel = sum(volumes_q.values())

    afficher(tableau(scenarios, probabilites), f"COMPARAISON DES SCENARIOS {sc.ANNEE_CIBLE}")
    print(f"\n  forward Cal-27 Base au T1 (22/09/2026) : {sc.FORWARD_CAL27_T1:.2f} EUR/MWh")
    print(f"  volume de reference (temperature normale) : {v_annuel:,.0f} MWh = 100 %")

    # ---- etape 3 : plausibilite du forward T2 anticipe
    sigma = sc.sigma_t2()
    print(f"\n{'=' * 78}\nETAPE 3 - FORWARD T2 ANTICIPE (methode alpha)\n{'=' * 78}")
    print(f"  bande de plausibilite CRE : {sc.FORWARD_CAL27_T1:.2f} +/- {sigma:.2f}"
          f" soit [{sc.FORWARD_CAL27_T1 - sigma:.2f} ; {sc.FORWARD_CAL27_T1 + sigma:.2f}]"
          f" a 1 sigma ({sc.VOLATILITE_CRE:.0%} annuel sur {sc.JOURS_T1_T2} jours)")
    lignes = []
    for an, s in scenarios.items():
        ligne = {"annee": an, "Level": s["niveau"]}
        for a in (0.2, ALPHA_T2, 0.6):
            ligne[f"alpha {a}"] = sc.forward_t2_anticipe(s["niveau"], a)
        ligne["alpha requis / reel"] = ((sc.FORWARD_CAL27_T2 - sc.FORWARD_CAL27_T1)
                                        / (s["niveau"] - sc.FORWARD_CAL27_T1))
        lignes.append(ligne)
    afficher(pd.DataFrame(lignes).set_index("annee"))
    print(f"  forward reel observe au T2 : {sc.FORWARD_CAL27_T2:.2f} EUR/MWh")

    # ---- etape 4 : mix de produits
    print(f"\n{'=' * 78}\nETAPE 4 - MIX DE PRODUITS, A COUVERTURE EGALE\n{'=' * 78}")
    h1_ref = STRATEGIES["Notre strategie 70/20/10"][0]
    index = reference.index
    for forme in ("cal", "trimestres", "trimestres+peak"):
        mix = construire_mix(h1_ref, volumes_q, index, forme)
        energie = sum(mw * heures_livrees(p, n, index) for (p, n), mw in mix.items())
        cout = cout_mix(mix, index, "T1")
        print(f"  {forme:<18} {len(mix)} produits | {energie:>9,.0f} MWh"
              f" ({energie / v_annuel:>5.1%} du volume) | {cout / 1e6:>6.2f} MEUR"
              f" | {cout / energie:>6.2f} EUR/MWh")
    print(f"\n  detail du mix retenu ({FORME}) pour {h1_ref:.0%} achetes au T1 :")
    afficher(decrire_mix(construire_mix(h1_ref, volumes_q, index), index, "T1"))

    # ---- etape 5 : marges, choix, couts de la protection
    strat = evaluer_strategies(scenarios, volumes_q, probabilites)
    afficher(strat, f"ETAPE 5 - MARGE PAR STRATEGIE (EUR/MWh, mix {FORME})")
    print(f"  prix de vente {PRIX_VENTE:.0f} | marge cible {MARGE_CIBLE:.0f}"
          f" | plancher {PLANCHER_RISQUE:.0f} | probabilites "
          + ", ".join(f"{an} {probabilites[an]:.0%}" for an in scenarios))

    choix = choisir(strat)
    if choix:
        print(f"  -> retenue : {choix} (esperance {strat.loc[choix, 'esperance']:.2f},"
              f" pire cas {strat.loc[choix, 'pire cas']:.2f})")
    else:
        print(f"  -> AUCUNE strategie ne tient le plancher de {PLANCHER_RISQUE:.0f} EUR/MWh :"
              f" le portefeuille est structurellement trop cher a {PRIX_VENTE:.0f} EUR/MWh.")

    ref = strat["couv. prevue %"].idxmin()
    prot = pd.DataFrame({
        "esperance cedee": strat.loc[ref, "esperance"] - strat["esperance"],
        "pire cas gagne": strat["pire cas"] - strat.loc[ref, "pire cas"]})
    prot["prix de la protection"] = (prot["esperance cedee"]
                                     / prot["pire cas gagne"].replace(0, np.nan))
    afficher(prot, f"COUT DE LA PROTECTION (reference : {ref})")

    print(f"\n{'=' * 78}\nSENSIBILITE DE LA DECISION\n{'=' * 78}")
    best = strat["pire cas"].idxmax()
    print(f"  meilleure protection possible : {best}"
          f" (pire cas {strat.loc[best, 'pire cas']:.2f} EUR/MWh)")
    print("  plancher du Conseil :")
    for p in sorted({-2.5, 0.0, 2.5, 5.0, PLANCHER_RISQUE, 7.5, 10.0}):
        c = choisir(strat, p)
        print(f"    {p:>5.1f} EUR/MWh -> {c or 'aucune strategie admissible'}")
    print("  pente b :")
    for nom, valeur in [("minimum annuel", min(s["b"] for s in brut.values())),
                        ("mutualisee", b),
                        ("maximum annuel", max(s["b"] for s in brut.values()))]:
        sc_b = {an: reajuster(s, valeur, sc.FORWARD_CAL27_T1 * s["multiplicateur_forward"])
                for an, s in scenarios.items()}
        t = evaluer_strategies(sc_b, volumes_q, probabilites)
        print(f"    b = {valeur:+.3f} ({nom:<15}) -> meilleure esperance :"
              f" {t['esperance'].idxmax()} | admissible : {choisir(t) or 'aucune'}")
    print("  alpha :")
    for a in (0.2, ALPHA_T2, 0.6):
        t = evaluer_strategies(scenarios, volumes_q, probabilites, alpha=a)
        print(f"    alpha = {a:.1f} -> meilleure esperance : {t['esperance'].idxmax()}"
              f" | admissible : {choisir(t) or 'aucune'}")
    print("  mix de produits :")
    for forme in ("cal", "trimestres", "trimestres+peak"):
        t = evaluer_strategies(scenarios, volumes_q, probabilites, forme=forme)
        print(f"    {forme:<18} -> meilleure esperance : {t['esperance'].idxmax()}"
              f" ({t['esperance'].max():.2f}) | admissible : {choisir(t) or 'aucune'}")

    tableau(scenarios, probabilites).to_csv(SORTIES / "comparaison_scenarios.csv",
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
    axes[0].set_ylabel("EUR/MWh"); axes[0].set_title(f"Prix spot {sc.ANNEE_CIBLE}"); axes[0].legend()
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
