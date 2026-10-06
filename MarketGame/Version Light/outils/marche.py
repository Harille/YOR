"""
OUTIL — LE MARCHE : prix EEX, scenarios de prix, methode alpha
...............................................................................
Ce que ca fait  : la table des prix EEX aux trois jalons (Base et Peak, Cal,
                  Q1-Q4, Jan-Jun), la construction d'un scenario de prix a
                  partir d'une annee historique (Level x Shape), la pente
                  prix-volume b, et le forward T2 anticipe par la methode alpha
                  avec son controle de plausibilite (sigma CRE).
Ce que ca lit   : donnees/historique/temperature_AAAA.csv et prix_AAAA.csv
Ce que ca ecrit : sorties/scenario_2021_2027.csv  (quand on le lance seul)
A changer ici   : EEX (les prix releves par le prof), ANNEE_HISTORIQUE,
                  PRIME_DE_RISQUE, VOLATILITE_CRE
Dans le rapport : etapes 8, 9 et 10
"""
import io
import unicodedata

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from outils import calendrier
from outils.demande import (ANNEE_CIBLE, SORTIES, entree, calculer_puissances,
                                construire_base, pas_horaire, reviser_t2)

ANNEE_HISTORIQUE = 2021
PRIME_DE_RISQUE = 0.03
VOLATILITE_CRE = 0.20          # volatilite annuelle des forwards annuels (estimation CRE)
JOURS_T1_T2 = 70               # du 22/09/2026 au 01/12/2026

# EEX French Power Futures 2027, prix de reglement en EUR/MWh (fichiers du prof)
# T1 = 22/09/2026   T2 = 01/12/2026   T3 = 31/12/2026
#            Base T1  Peak T1  Base T2  Peak T2  Base T3  Peak T3
EEX = {
    "Cal-27": (83.31, 95.59, 73.70, 83.74, 78.37, 90.31),
    "Q1-27": (139.00, 171.94, 119.54, 146.15, 133.88, 166.61),
    "Q2-27": (45.18, 36.50, 42.47, 35.04, 43.32, 35.39),
    "Q3-27": (61.09, 51.62, 56.20, 48.52, 56.76, 49.01),
    "Q4-27": (88.78, 123.72, 77.24, 106.40, 80.33, 111.72),
    "Jan-27": (159.54, 202.58, 135.42, 169.95, 156.25, 199.83),
    "Feb-27": (153.15, 201.51, 131.53, 171.07, 147.87, 196.07),
    "Mar-27": (105.63, 118.25, 92.83, 102.75, 98.87, 110.66),
    "Apr-27": (59.51, 43.02, 55.44, 40.88, 57.02, 41.53),
    "May-27": (39.33, 26.13, 37.03, 25.09, 37.71, 25.24),
    "Jun-27": (36.90, 39.89, 35.12, 38.70, 35.42, 38.93),
}
JALONS = {"T1": 0, "T2": 2, "T3": 4}
FORWARD_CAL27_T1 = EEX["Cal-27"][0]
FORWARD_CAL27_T2 = EEX["Cal-27"][2]
FORWARD_CAL27_T3 = EEX["Cal-27"][4]


def prix_eex(produit, nature="Base", jalon="T1"):
    return EEX[produit][{"Base": 0, "Peak": 1}[nature] + JALONS[jalon]]


def forward_t2_anticipe(niveau, alpha, forward_t1=FORWARD_CAL27_T1):
    """Etape 3 du cours : Forward(T2) = Forward(T1) + alpha x (Level - Forward(T1))."""
    return forward_t1 + alpha * (niveau - forward_t1)


def sigma_t2(forward_t1=FORWARD_CAL27_T1):
    """Ecart-type plausible du forward au T2, deduit de la volatilite CRE."""
    return forward_t1 * VOLATILITE_CRE * np.sqrt(JOURS_T1_T2 / 365.0)


def _normaliser(texte):
    texte = unicodedata.normalize("NFKD", str(texte))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return "".join(c for c in texte.lower() if c.isalnum())


def _fichier(genre, annee):
    chemin = entree("historique", f"{genre}_{annee}.csv")
    if not chemin.exists():
        raise FileNotFoundError(f"{chemin} est introuvable.")
    return chemin


def charger_temperature_historique(chemin):
    df = pd.read_csv(chemin, sep=None, engine="python", encoding="utf-8-sig")

    def colonne(*motifs):
        for c in df.columns:
            if all(m in _normaliser(c) for m in motifs):
                return c
        raise KeyError(f"Colonne {motifs} introuvable parmi {list(df.columns)}")

    out = pd.DataFrame({
        "HORODATE": pd.to_datetime(df[colonne("horodate")], format="ISO8601", utc=True)
                      .dt.tz_convert("Europe/Paris"),
        "t_realisee": pd.to_numeric(df[colonne("realisee", "lissee")], errors="coerce"),
        "t_normale": pd.to_numeric(df[colonne("normale", "lissee")], errors="coerce")})
    out = out.drop_duplicates(subset="HORODATE", keep="first").sort_values("HORODATE")
    out["t_realisee"] = out["t_realisee"].fillna(out["t_normale"])
    return out.set_index("HORODATE")


def charger_prix_entsoe(chemin):
    df = pd.read_csv(chemin, encoding="utf-8-sig")
    if df.shape[1] == 1 and "," in df.columns[0]:          # format double-encode
        texte = "\n".join([df.columns[0]] + df.iloc[:, 0].astype(str).tolist())
        df = pd.read_csv(io.StringIO(texte))
    df.columns = [c.strip() for c in df.columns]

    col_temps = next(c for c in df.columns if "mtu" in c.lower())
    col_prix = next(c for c in df.columns if "day-ahead price" in c.lower())
    debut = df[col_temps].astype(str).str.split(" - ").str[0].str.strip()

    horodate = None
    for fmt in ("%d.%m.%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        essai = pd.to_datetime(debut, format=fmt, errors="coerce")
        if essai.notna().all():
            horodate = essai
            break
    if horodate is None:
        horodate = pd.to_datetime(debut, dayfirst=True, errors="coerce")

    serie = pd.Series(pd.to_numeric(df[col_prix], errors="coerce").to_numpy(),
                      index=pd.DatetimeIndex(horodate), name="spot")
    serie = serie[~serie.index.duplicated(keep="first")].dropna().sort_index()
    if "utc" in col_temps.lower():
        serie.index = serie.index.tz_localize("UTC").tz_convert("Europe/Paris")
    else:
        serie.index = serie.index.tz_localize("Europe/Paris", ambiguous=True,
                                              nonexistent="shift_forward")
    return serie.sort_index()


def _cle_calendaire(index):
    return (index.month.astype("int64") * 1_000_000 + index.day.astype("int64") * 10_000
            + index.hour.astype("int64") * 60 + index.minute.astype("int64")).to_numpy()


def _reindexer_par_calendrier(source, index_cible):
    src = source.sort_index()
    cles = _cle_calendaire(src.index)
    garde = np.concatenate([[True], np.diff(cles) != 0])
    cles, valeurs = cles[garde], src.to_numpy()[garde]
    pos = np.searchsorted(cles, _cle_calendaire(index_cible), side="right") - 1
    return pd.Series(valeurs[pos].astype(float), index=index_cible)


def injecter_temperature(cible, source):
    out = cible.copy()
    valeurs = _reindexer_par_calendrier(source, out.index)
    valeurs = valeurs.fillna(out["temperature_normale_lissee_degc"])
    out["temperature_realisee_lissee_degc"] = valeurs.to_numpy()
    return out


def volumes_journaliers(df):
    h, j = pas_horaire(df), df.index.date
    return pd.DataFrame({
        "volume_reel": df["P_dyn_totale_kW"].groupby(j).sum() * h / 1000.0,
        "volume_normal": df["P_totale_kW"].groupby(j).sum() * h / 1000.0})


def anomalies(volumes, prix_horaire):
    prix_jour = prix_horaire.groupby(prix_horaire.index.date).mean()
    prix_jour.index = pd.to_datetime(prix_jour.index)
    moyenne_mois = prix_jour.groupby(prix_jour.index.month).transform("mean")

    tab = pd.DataFrame({"prix": prix_jour,
                        "anomalie_prix": (prix_jour - moyenne_mois) / moyenne_mois})
    vol = volumes.copy()
    vol.index = pd.to_datetime(vol.index)
    tab = tab.join(vol, how="inner")
    tab["anomalie_volume"] = (tab["volume_reel"] - tab["volume_normal"]) / tab["volume_normal"]
    return tab.dropna()


def pente_prix_volume(tab):
    """Regression anomalie_prix = b x anomalie_volume. Qualite = r et r carre."""
    x = tab["anomalie_volume"].to_numpy()
    y = tab["anomalie_prix"].to_numpy()
    b = np.cov(x, y, ddof=0)[0, 1] / np.var(x)
    r = np.corrcoef(x, y)[0, 1]
    n = len(x)
    # erreur type de la pente : sert a dire si b est significatif
    residus = y - (y.mean() + b * (x - x.mean()))
    se = np.sqrt((residus ** 2).sum() / (n - 2) / ((x - x.mean()) ** 2).sum())
    return {"b": b, "r": r, "r2": r ** 2, "n": n, "se": se, "t": b / se}


def scenario_spot(prix_hist, niveau, index_cible):
    """Level x Shape : la forme historique est normalisee a 1, le niveau vient du forward."""
    forme = prix_hist / prix_hist.mean()
    valeurs = _reindexer_par_calendrier(forme, index_cible).fillna(1.0)
    return pd.Series(niveau * valeurs.to_numpy(), index=index_cible, name="spot")


def construire_scenario(annee_hist, base, b_impose=None, forward=None, bavard=True):
    forward = FORWARD_CAL27_T1 if forward is None else forward
    temp = charger_temperature_historique(_fichier("temperature", annee_hist))["t_realisee"]
    prix = charger_prix_entsoe(_fichier("prix", annee_hist))

    hist = injecter_temperature(calendrier.projeter(base, annee_hist), temp)
    tab = anomalies(volumes_journaliers(calculer_puissances(hist)), prix)
    reg = pente_prix_volume(tab[tab.index.month.isin([1, 2, 3, 11, 12])])
    b = reg["b"] if b_impose is None else b_impose

    cible_normal = calculer_puissances(calendrier.projeter(base, ANNEE_CIBLE))
    cible_scen = calculer_puissances(
        injecter_temperature(calendrier.projeter(base, ANNEE_CIBLE), temp))
    cible_scen_t2 = reviser_t2(cible_scen)

    h = pas_horaire(cible_normal)
    e_normal = cible_normal["P_totale_kW"].sum() * h / 1000.0
    e_scen = cible_scen["P_dyn_totale_kW"].sum() * h / 1000.0
    e_normal_t2 = reviser_t2(cible_normal)["P_totale_kW"].sum() * h / 1000.0
    e_scen_t2 = cible_scen_t2["P_dyn_totale_kW"].sum() * h / 1000.0
    anomalie = e_scen / e_normal - 1

    niveau = forward * (1 - PRIME_DE_RISQUE) * (1 + b * anomalie)
    res = pd.DataFrame({
        "charge_MW": cible_scen["P_dyn_totale_kW"].resample("h").mean() / 1000.0,
        "charge_T2_MW": cible_scen_t2["P_dyn_totale_kW"].resample("h").mean() / 1000.0,
        "charge_normale_MW": cible_normal["P_totale_kW"].resample("h").mean() / 1000.0,
        "charge_normale_T2_MW": reviser_t2(cible_normal)["P_totale_kW"]
                                .resample("h").mean() / 1000.0})
    res["spot_EUR_MWh"] = scenario_spot(prix, niveau, res.index)
    res["cout_EUR"] = res["charge_MW"] * res["spot_EUR_MWh"]

    prix_pondere = res["cout_EUR"].sum() / res["charge_MW"].sum()
    if bavard:
        print(f"  temperature moyenne : {temp.mean():.2f} C"
              f" | prix historique : {prix.mean():.2f} EUR/MWh")
        print(f"  b mesure sur l'hiver : {reg['b']:+.3f} | r = {reg['r']:+.3f}"
              f" | r2 = {reg['r2']:.3f} | t = {reg['t']:+.1f} | n = {reg['n']} jours")
        print(f"  volume {ANNEE_CIBLE} : {e_scen:,.0f} MWh"
              f" ({anomalie:+.2%} vs temperature normale)")
        print(f"  Level = {forward:.2f} x (1-{PRIME_DE_RISQUE:.0%})"
              f" x (1 + {b:+.3f} x {anomalie:+.2%}) = {niveau:.2f} EUR/MWh")

    return {"annee": annee_hist, "temperature_moyenne": temp.mean(),
            "prix_historique_moyen": prix.mean(), "b": reg["b"], "b_retenu": b,
            "correlation": reg["r"], "r2": reg["r2"], "t_student": reg["t"],
            "n_jours": reg["n"], "energie_normale": e_normal, "energie_scenario": e_scen,
            "energie_normale_T2": e_normal_t2, "energie_scenario_T2": e_scen_t2,
            "anomalie_volume": anomalie, "niveau": niveau,
            "prix_moyen": res["spot_EUR_MWh"].mean(), "prix_pondere": prix_pondere,
            "surcout_prix_volume": prix_pondere - res["spot_EUR_MWh"].mean(),
            "cout_total": res["cout_EUR"].sum(),
            "pointe_MW": cible_scen["P_dyn_totale_kW"].max() / 1000.0,
            "courbe": res, "anomalies": tab}


def tracer(res):
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    axes[0].plot(res.index, res["charge_MW"], lw=0.6, color="tab:green")
    axes[0].set_ylabel("MW"); axes[0].set_title(f"Charge {ANNEE_CIBLE}")
    axes[1].plot(res.index, res["spot_EUR_MWh"], lw=0.6, color="tab:red")
    axes[1].set_ylabel("EUR/MWh"); axes[1].set_title(f"Spot {ANNEE_CIBLE}")
    quot = res["cout_EUR"].resample("D").sum() / 1e3
    axes[2].bar(quot.index, quot, width=1, color="tab:blue")
    axes[2].set_ylabel("kEUR/jour"); axes[2].set_xlabel("Date")
    axes[2].set_title("Cout journalier au spot")
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout(); plt.show()


def main():
    base = construire_base()
    print(f"\n{'=' * 70}\nSCENARIO - meteo et prix de {ANNEE_HISTORIQUE},"
          f" portefeuille {ANNEE_CIBLE}\n{'=' * 70}")
    sc = construire_scenario(ANNEE_HISTORIQUE, base)

    print("\n--- Resultat du scenario ---")
    print(f"  prix spot moyen                  : {sc['prix_moyen']:>10,.2f} EUR/MWh")
    print(f"  prix moyen PONDERE par la charge : {sc['prix_pondere']:>10,.2f} EUR/MWh")
    print(f"  surcout prix-volume              : {sc['surcout_prix_volume']:>+10.2f} EUR/MWh"
          f"  ({sc['prix_pondere'] / sc['prix_moyen'] - 1:+.2%})")
    print(f"  cout total au spot               : {sc['cout_total'] / 1e6:>10,.2f} MEUR")
    print(f"  forward T2 anticipe (alpha 0.5)  : "
          f"{forward_t2_anticipe(sc['niveau'], 0.5):>10,.2f} EUR/MWh"
          f"   (reel : {FORWARD_CAL27_T2:.2f})")

    sortie = SORTIES / f"scenario_{ANNEE_HISTORIQUE}_{ANNEE_CIBLE}.csv"
    sc["courbe"].to_csv(sortie, sep=";", decimal=",")
    print(f"\n-> Export : sorties/{sortie.name}")
    return sc["courbe"]


if __name__ == "__main__":
    tracer(main())
