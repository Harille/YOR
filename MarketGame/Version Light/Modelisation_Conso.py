from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import calendrier

ANNEE_CIBLE = 2027

PARAMS = {                                      # portefeuille au T1 (22/09/2026)
    "RES1": {"nb_clients": 200_000, "puissance_souscrite": 4.5, "theta": 0.0521},
    "PRO1": {"nb_clients": 5_000, "puissance_souscrite": 36.0, "theta": 0.08004},
}
REVISION_T2 = {"RES1": -0.059, "PRO1": -0.083}  # Commercial forecast du 01/12/2026

COEF_COL = "COEFFICIENT_PREPARE"
T_SEUIL = 15.0
AFFINER_AU_QUART_HEURE = True

DOSSIER = Path(__file__).parent
FICHIERS = {
    "RES1": DOSSIER / "RES1_BASE.csv",
    "PRO1": DOSSIER / "PRO1_BASE.csv",
    "gradients": DOSSIER / "gradients.csv",
    "temperature": DOSSIER / "temperature_2025.csv",
}


def fud(profil):
    p = PARAMS[profil]
    return p["puissance_souscrite"] * p["theta"]


def _horodate(serie):
    return pd.to_datetime(serie, format="ISO8601", utc=True).dt.tz_convert("Europe/Paris")


def affiner_au_quart_heure(demi_horaire, quart_horaire):
    demi_heure = quart_horaire.index.tz_convert("UTC").floor("30min")
    ratio = quart_horaire / quart_horaire.groupby(demi_heure).transform("mean")
    return demi_horaire * ratio


def charger_coefficients(profil):
    df = pd.read_csv(FICHIERS[profil], sep=",", decimal=".")
    df["HORODATE"] = _horodate(df["HORODATE"])
    df = df.drop_duplicates(subset="HORODATE", keep="first").sort_values("HORODATE")
    df = df.set_index("HORODATE")
    coef = df[COEF_COL]
    if AFFINER_AU_QUART_HEURE and "COEFFICIENT_DYNAMIQUE" in df.columns:
        coef = affiner_au_quart_heure(coef, df["COEFFICIENT_DYNAMIQUE"])
    return coef.rename(f"coef_{profil}").reset_index()


def charger_gradients():
    df = pd.read_csv(FICHIERS["gradients"], sep=";", decimal=".")
    df["HORODATE"] = _horodate(df["HORODATE"])
    df = df.drop_duplicates(subset="HORODATE", keep="first")
    df = df.rename(columns={"RES1_BASE": "grad_RES1", "PRO1_BASE": "grad_PRO1"})
    return df[["HORODATE", "grad_RES1", "grad_PRO1"]].sort_values("HORODATE")


def charger_temperatures():
    df = pd.read_csv(FICHIERS["temperature"], sep=",", decimal=".")
    df = df.rename(columns={"Horodate": "HORODATE"})
    df["HORODATE"] = _horodate(df["HORODATE"])
    df = df.drop_duplicates(subset="HORODATE", keep="first")
    for col in ("temperature_realisee_lissee_degc", "temperature_normale_lissee_degc"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["temperature_realisee_lissee_degc"] = df["temperature_realisee_lissee_degc"].fillna(
        df["temperature_normale_lissee_degc"])
    return df[["HORODATE", "temperature_realisee_lissee_degc",
               "temperature_normale_lissee_degc"]].sort_values("HORODATE")


def construire_base():
    df = charger_coefficients("RES1")
    for autre in (charger_coefficients("PRO1"), charger_gradients(), charger_temperatures()):
        df = df.merge(autre, on="HORODATE", how="inner")
    return df.set_index("HORODATE").sort_index()


def coefficient_meteo(gradient, t_normale, t_realisee, t_seuil=T_SEUIL):
    T, Tn, Ts = t_realisee, t_normale, t_seuil
    cm = np.select(
        [(T < Ts) & (Tn < Ts), (T < Ts) & (Tn >= Ts), (Tn < Ts) & (T >= Ts), (T >= Ts) & (Tn >= Ts)],
        [1 + gradient * (Tn - T), 1 + gradient * (Ts - T), 1 + gradient * (Tn - Ts), 1.0],
        default=np.nan)
    return pd.Series(cm, index=t_realisee.index)


def calculer_puissances(df):
    out = df.copy()
    for profil in ("RES1", "PRO1"):
        f, nb = fud(profil), PARAMS[profil]["nb_clients"]
        coef = out[f"coef_{profil}"]
        out[f"CM_{profil}"] = coefficient_meteo(
            out[f"grad_{profil}"], out["temperature_normale_lissee_degc"],
            out["temperature_realisee_lissee_degc"])
        out[f"P_{profil}_kW"] = nb * f * coef
        out[f"P_dyn_{profil}_kW"] = nb * f * coef * out[f"CM_{profil}"]
    return _totaliser(out)


def _totaliser(out):
    out["P_totale_kW"] = out["P_RES1_kW"] + out["P_PRO1_kW"]
    out["P_dyn_totale_kW"] = out["P_dyn_RES1_kW"] + out["P_dyn_PRO1_kW"]
    return out


def reviser_t2(df):
    """Portefeuille du 01/12/2026 : la puissance est lineaire en nombre de clients."""
    out = df.copy()
    for profil, variation in REVISION_T2.items():
        for col in (f"P_{profil}_kW", f"P_dyn_{profil}_kW"):
            out[col] = df[col] * (1 + variation)
    return _totaliser(out)


def pas_horaire(df):
    return (df.index[1] - df.index[0]).total_seconds() / 3600.0


def energies(df):
    cols = [c for c in df.columns if c.endswith("_kW")]
    return (df[cols].sum() * pas_horaire(df) / 1000.0).rename("MWh")


def trimestres(df, col="P_dyn_totale_kW"):
    return df[col].groupby(df.index.quarter).sum() * pas_horaire(df) / 1000.0


def mois(df, col="P_dyn_totale_kW"):
    return df[col].groupby(df.index.month).sum() * pas_horaire(df) / 1000.0


def masque_peak(index):
    """Heures Peak EEX : lundi-vendredi 08h-20h, jours feries inclus."""
    return (index.weekday < 5) & (index.hour >= 8) & (index.hour < 20)


def peak_offpeak(df, col="P_dyn_totale_kW"):
    h, pk = pas_horaire(df), masque_peak(df.index)
    return {"peak_MWh": df.loc[pk, col].sum() * h / 1000.0,
            "offpeak_MWh": df.loc[~pk, col].sum() * h / 1000.0,
            "peak_MW_moyen": df.loc[pk, col].mean() / 1000.0,
            "offpeak_MW_moyen": df.loc[~pk, col].mean() / 1000.0,
            "heures_peak": float(pk.sum()) * h}


def thermosensibilite(df):
    """Sensibilite du portefeuille, en MW par degre perdu (gradient x puissance)."""
    s = sum(df[f"P_{p}_kW"] * df[f"grad_{p}"] for p in PARAMS) / 1000.0
    s = s.where(df["temperature_normale_lissee_degc"] < T_SEUIL, 0.0)
    return s.rename("MW_par_degre")


def resume(df, titre):
    print(f"\n{'=' * 70}\n{titre}\n{'=' * 70}")
    print(f"Periode : {df.index.min():%d/%m/%Y} -> {df.index.max():%d/%m/%Y}"
          f"  ({len(df):,} pas de {pas_horaire(df) * 60:.0f} min)")
    plat = all((df[f"CM_{p}"] - 1).abs().max() < 1e-12 for p in PARAMS)
    print("Scenario : temperature NORMALE (CM = 1)" if plat else "Scenario : temperature REALISEE")

    print("\nPuissances (MW)")
    for col in ("P_dyn_RES1_kW", "P_dyn_PRO1_kW", "P_dyn_totale_kW"):
        s = df[col] / 1000.0
        print(f"  {col[:-3]:<18} moyenne {s.mean():8.2f} | pointe {s.max():8.2f}"
              f" le {s.idxmax():%d/%m %H:%M} | creux {s.min():8.2f}")

    e = energies(df)
    print("\nEnergie (MWh)")
    for profil in ("RES1", "PRO1"):
        print(f"  {profil:<18} {e[f'P_dyn_{profil}_kW']:>12,.0f}"
              f"  ({100 * e[f'P_dyn_{profil}_kW'] / e['P_dyn_totale_kW']:.1f} %)")
    print(f"  {'TOTAL = 100 %':<18} {e['P_dyn_totale_kW']:>12,.0f}   <- base de tous les ratios")
    if not plat:
        print(f"  effet meteo : {100 * (e['P_dyn_totale_kW'] / e['P_totale_kW'] - 1):+.1f} %")

    an = df.index[0].year
    print(f"\nVolumes mensuels (MWh)")
    m = mois(df)
    for debut in (1, 7):
        print("   " + " ".join(f"{pd.Timestamp(2000, k, 1):%b}" + f" {m[k]:>7,.0f}"
                               for k in range(debut, debut + 6)))
    print(f"\nVolumes trimestriels (MWh) - produits Q1-{an % 100} a Q4-{an % 100}")
    print("   " + " | ".join(f"Q{q}-{an % 100} {v:>9,.0f}" for q, v in trimestres(df).items()))

    po = peak_offpeak(df)
    tot = po["peak_MWh"] + po["offpeak_MWh"]
    print(f"\nPeak / Off-peak (Peak = lun-ven 08h-20h, {po['heures_peak']:,.0f} h)")
    print(f"  Peak     {po['peak_MWh']:>10,.0f} MWh ({100 * po['peak_MWh'] / tot:>4.1f} %)"
          f" | puissance moyenne {po['peak_MW_moyen']:6.2f} MW")
    print(f"  Off-peak {po['offpeak_MWh']:>10,.0f} MWh ({100 * po['offpeak_MWh'] / tot:>4.1f} %)"
          f" | puissance moyenne {po['offpeak_MW_moyen']:6.2f} MW")
    print(f"  ratio de forme Peak/Off-peak : {po['peak_MW_moyen'] / po['offpeak_MW_moyen']:.3f}")

    ts = thermosensibilite(df)
    print(f"\nThermosensibilite : {ts[ts > 0].mean():.2f} MW/C en moyenne de chauffe"
          f" | max {ts.max():.2f} le {ts.idxmax():%d/%m %H:%M}")


def tracer(df, debut=None, fin=None, titre=""):
    sous = df.loc[debut:fin] if (debut or fin) else df
    meteo = (df["CM_RES1"] - 1).abs().max() > 1e-12
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    for ax, (col_n, col_d, lib, coul) in zip(axes, [
        ("P_RES1_kW", "P_dyn_RES1_kW", f"RES1 - {PARAMS['RES1']['nb_clients']:,} clients", "tab:blue"),
        ("P_PRO1_kW", "P_dyn_PRO1_kW", f"PRO1 - {PARAMS['PRO1']['nb_clients']:,} clients", "tab:orange"),
        ("P_totale_kW", "P_dyn_totale_kW", "Portefeuille total", "tab:green")]):
        if meteo:
            ax.plot(sous.index, sous[col_n] / 1000, lw=0.7, alpha=0.55, color="grey",
                    label="temperature normale")
        ax.plot(sous.index, sous[col_d] / 1000, lw=0.9, color=coul,
                label="temperature realisee" if meteo else "temperature normale")
        ax.set_ylabel("MW"); ax.set_title(lib); ax.legend(loc="upper right"); ax.grid(alpha=0.3)
    axes[-1].set_xlabel("Horodate")
    fig.suptitle(titre or "Courbe de charge")
    fig.tight_layout(); plt.show()


def main():
    base = construire_base()
    an_source = base.index[0].year

    print("\nParametres du portefeuille (etape 1 : dimensionnement du profil Enedis)")
    for profil, p in PARAMS.items():
        print(f"  {profil} : {p['nb_clients']:>8,} clients | PS = {p['puissance_souscrite']:>5} kVA"
              f" | Theta = {p['theta']} | FUD = PS x Theta = {fud(profil):.5f} kW")

    hist = calculer_puissances(base)
    resume(hist, f"BACKTEST {an_source} - temperature realisee")
    hist.to_csv(DOSSIER / f"courbe_de_charge_{an_source}.csv", sep=";", decimal=",")

    if ANNEE_CIBLE is None or ANNEE_CIBLE == an_source:
        return hist, hist

    cible = calculer_puissances(calendrier.projeter(base, ANNEE_CIBLE))
    resume(cible, f"LIVRABLE T1 {ANNEE_CIBLE} - temperature normale, portefeuille au 22/09/2026")
    cible.to_csv(DOSSIER / f"courbe_de_charge_{ANNEE_CIBLE}.csv", sep=";", decimal=",")

    t2 = reviser_t2(cible)
    e1 = energies(cible)["P_dyn_totale_kW"]
    e2 = energies(t2)["P_dyn_totale_kW"]
    resume(t2, f"LIVRABLE T2 {ANNEE_CIBLE} - portefeuille revise au 01/12/2026")
    print(f"\n  revision commerciale : {e1:,.0f} -> {e2:,.0f} MWh ({e2 / e1 - 1:+.2%})")
    t2.to_csv(DOSSIER / f"courbe_de_charge_{ANNEE_CIBLE}_T2.csv", sep=";", decimal=",")

    print(f"\n-> Exports : courbe_de_charge_{an_source}.csv, courbe_de_charge_{ANNEE_CIBLE}.csv,"
          f" courbe_de_charge_{ANNEE_CIBLE}_T2.csv")
    return hist, cible


if __name__ == "__main__":
    backtest, livrable = main()
    tracer(livrable, titre=f"Courbe de charge {ANNEE_CIBLE} - annee")
    tracer(livrable, f"{ANNEE_CIBLE}-01-11", f"{ANNEE_CIBLE}-01-17", titre="Semaine type d'hiver")
    tracer(livrable, f"{ANNEE_CIBLE}-01-01", f"{ANNEE_CIBLE}-01-01",
           titre="1er janvier 2027 - vendredi ferie")
