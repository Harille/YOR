"""
OUTIL — LA COUVERTURE : produits EEX, mix, marge, strategies
...............................................................................
Ce que ca fait  : tout ce qui est commun aux trois jalons. Les fenetres de
                  livraison des produits (Cal, trimestres, mois, Base et Peak),
                  la construction d'un mix a partir d'un taux de couverture,
                  son cout, la marge d'un scenario, et le jeu de scenarios
                  (meteo + choc fondamental) avec leurs probabilites.
                  C'est ici que les trois jalons puisent : t1, t2 et t3
                  appellent les MEMES fonctions, avec des prix differents.
Ce que ca lit   : rien directement (passe par outils/demande et outils/marche)
Ce que ca ecrit : rien, c'est une bibliotheque
A changer ici   : les parametres imposes par le Conseil (PRIX_VENTE 95,
                  MARGE_CIBLE 10, PLANCHER_RISQUE 5), STRATEGIES, ANNEES,
                  CHOC_FONDAMENTAL, PROBA_CHOC, ALPHA_T2, FORME
Dans le rapport : etapes 11 et 12
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from outils import marche
from outils.demande import SORTIES, construire_base, masque_peak

ANNEES = [2021, 2023, 2024]
MOIS_HIVER = [1, 2, 3, 11, 12]

PRIX_VENTE = 95.0          # EUR/MWh, impose par le Conseil
MARGE_CIBLE = 10.0         # EUR/MWh
PLANCHER_RISQUE = 5.0      # EUR/MWh, pire cas minimum

# Les trois profils de risque du cours (EM_4 p.25). Les guidelines imposent le
# profil Prudent (plancher = MARGE_CIBLE / 2 = 5), mais les deux autres servent
# a montrer ce qui bascule quand le Conseil accepte plus de risque.
PROFILS_RISQUE = {
    "Prudent  (WCM >= cible/2)": MARGE_CIBLE / 2,
    "Balanced (WCM >= 0)": 0.0,
    "Risky    (WCM >= -5)": -5.0,
}
ALPHA_T2 = 0.50            # part du scenario deja dans les prix au 01/12/2026
FORME = "trimestres"       # "cal" | "trimestres" | "trimestres+peak"

# Scenario de choc de NIVEAU, hors meteo (gaz, CO2, disponibilite nucleaire, demande).
# Indispensable : sans lui, le Level vaut toujours forward x (1 - prime), donc le spot
# est espere moins cher que le forward et le modele conclut mecaniquement "ne jamais se
# couvrir". +20 % = un ecart-type, c'est la volatilite annuelle estimee par la CRE.
# Les chocs vont par paire : un fondamental peut faire monter le prix comme le faire
# baisser. N'en garder qu'un seul fausserait la lecture du risque dans les deux sens.
CHOC_FONDAMENTAL = 0.20    # 0.0 pour desactiver les deux chocs
PROBA_CHOC = 0.15          # probabilite de CHAQUE choc (hausse et baisse)

STRATEGIES = {             # (part achetee a T1, part planifiee pour T2) - le reste au SPOT
    "Notre strategie 70/20/10": (0.70, 0.20),
    "Variante 50/25/25":        (0.50, 0.25),
    "A - front loaded":         (0.50, 0.40),
    "B - peu couverte":         (0.40, 0.40),
    "C - totalement couverte":  (0.40, 0.60),
    "D - back loaded":          (0.40, 0.50),
    "E - 80/10/10":             (0.80, 0.10),
    "F - 80/15/5":              (0.80, 0.15),
    "G - 90/5/5":               (0.90, 0.05),
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
    return sum(mw * marche.prix_eex(p, n, jalon) * heures_livrees(p, n, index)
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
               f"prix {jalon}": marche.prix_eex(p, n, jalon),
               "cout MEUR": mw * marche.prix_eex(p, n, jalon) * heures_livrees(p, n, index) / 1e6}
              for (p, n), mw in sorted(mix.items())]
    return pd.DataFrame(lignes)


# ------------------------------------------------------------------ scenarios
def annees_disponibles(annees):
    ok = []
    for an in annees:
        try:
            marche._fichier("temperature", an)
            marche._fichier("prix", an)
            ok.append(an)
        except FileNotFoundError:
            print(f"  [ignore] {an} : temperature ou prix manquant")
    return ok


def pente_mutualisee(scenarios):
    paquet = pd.concat([s["anomalies"][s["anomalies"].index.month.isin(MOIS_HIVER)]
                        for s in scenarios.values()])
    return marche.pente_prix_volume(paquet)


def nom_du_choc(signe):
    """Le nom d\'un scenario de choc : +1 pour la hausse, -1 pour la baisse."""
    return f"choc {signe * CHOC_FONDAMENTAL:+.0%}"


def construire_jeu(base, annees, forward=None, bavard=True):
    """Les scenarios meteo, la pente mutualisee, les deux chocs et les probabilites."""
    forward = marche.FORWARD_CAL27_T1 if forward is None else forward
    brut = {}
    for an in annees:
        if bavard:
            print(f"\n--- scenario {an} ---")
        brut[an] = marche.construire_scenario(an, base, bavard=bavard)
    b = pente_mutualisee(brut)["b"]

    scenarios = {an: reajuster(s, b, forward) for an, s in brut.items()}
    if CHOC_FONDAMENTAL:
        # Deux chocs de niveau, symetriques. La hausse est portee par l'annee la plus
        # froide (le pire cumul prix x volume), la baisse par la plus douce. Le niveau
        # de prix bouge, le volume ne bouge pas : un choc de fondamentaux (gaz, CO2,
        # parc nucleaire) n'est pas un evenement meteo.
        froid = min(brut, key=lambda a: brut[a]["temperature_moyenne"])
        doux = max(brut, key=lambda a: brut[a]["temperature_moyenne"])
        for signe, origine in ((+1, froid), (-1, doux)):
            multiplicateur = 1 + signe * CHOC_FONDAMENTAL
            nom = nom_du_choc(signe)
            scenarios[nom] = reajuster(brut[origine], b, forward * multiplicateur)
            scenarios[nom]["multiplicateur_forward"] = multiplicateur
            scenarios[nom]["origine"] = origine
        reste = (1 - 2 * PROBA_CHOC) / len(brut)
        probabilites = ({an: reste for an in brut}
                        | {nom_du_choc(+1): PROBA_CHOC, nom_du_choc(-1): PROBA_CHOC})
    else:
        probabilites = {an: 1 / len(brut) for an in brut}
    return scenarios, brut, b, probabilites


def reajuster(scenario, b, forward):
    """Re-ancre le Level sur un forward et une pente donnes, sans refaire la projection."""
    niveau = forward * (1 - marche.PRIME_DE_RISQUE) * (1 + b * scenario["anomalie_volume"])
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
    forward_t2 = marche.forward_t2_anticipe(scenario["niveau"], alpha)

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
                       "fwd T2 anticipe": marche.forward_t2_anticipe(s["niveau"], ALPHA_T2),
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

