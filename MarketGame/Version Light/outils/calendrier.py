"""
OUTIL — LE CALENDRIER : jours feries, types de jour, projection d'une annee
...............................................................................
Ce que ca fait  : donne a chaque horodate son type de jour (lundi..dimanche, plus
                  un 7e type pour les feries), apparie chaque jour de l'annee
                  cible avec un jour de MEME TYPE de l'annee source, et projette
                  une courbe d'une annee sur une autre.
                  Paques est calculee par l'algorithme de Meeus/Jones/Butcher.
Ce que ca lit   : rien, c'est du calcul pur
Ce que ca ecrit : rien, c'est une bibliotheque
Qui s'en sert   : outils/demande.py, outils/marche.py, t3_spot.py
Dans le rapport : etapes 6 et 7
"""
import datetime as dt
import pandas as pd


def _paques(annee):
    a = annee % 19
    b, c = divmod(annee, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois, jour = divmod(h + l - 7 * m + 114, 31)
    return dt.date(annee, mois, jour + 1)


def jours_feries(annee):
    p = _paques(annee)
    return {dt.date(annee, 1, 1), p + dt.timedelta(days=1), dt.date(annee, 5, 1),
            dt.date(annee, 5, 8), p + dt.timedelta(days=39), p + dt.timedelta(days=50),
            dt.date(annee, 7, 14), dt.date(annee, 8, 15), dt.date(annee, 11, 1),
            dt.date(annee, 11, 11), dt.date(annee, 12, 25)}


def _type_jour(d, feries):
    return 7 if d in feries else d.weekday()


def apparier_jours(an_source, an_cible):
    f_src, f_cib = jours_feries(an_source), jours_feries(an_cible)
    src = pd.date_range(f"{an_source}-01-01", f"{an_source}-12-31", freq="D").date
    cib = pd.date_range(f"{an_cible}-01-01", f"{an_cible}-12-31", freq="D").date

    par_type = {}
    for d in src:
        par_type.setdefault(_type_jour(d, f_src), []).append(d)

    appariement = {}
    for d in cib:
        candidats = par_type.get(_type_jour(d, f_cib)) or par_type[6]
        ref = d.timetuple().tm_yday
        appariement[d] = min(candidats, key=lambda s: min(
            abs(s.timetuple().tm_yday - ref), 365 - abs(s.timetuple().tm_yday - ref)))
    return appariement


def _appariement_calendaire(an_source, an_cible):
    src = set(pd.date_range(f"{an_source}-01-01", f"{an_source}-12-31", freq="D").date)
    out = {}
    for d in pd.date_range(f"{an_cible}-01-01", f"{an_cible}-12-31", freq="D").date:
        try:
            jumeau = dt.date(an_source, d.month, d.day)
        except ValueError:
            jumeau = dt.date(an_source, d.month, d.day - 1)
        out[d] = jumeau if jumeau in src else dt.date(an_source, d.month, d.day - 1)
    return out


def projeter(df, an_cible, tz="Europe/Paris"):
    an_source = df.index[0].year
    pas = df.index[1] - df.index[0]
    cible_index = pd.date_range(f"{an_cible}-01-01", f"{an_cible}-12-31 23:59", freq=pas, tz=tz)
    source_par_jour = {j: g for j, g in df.groupby(df.index.date)}

    def assembler(appariement):
        morceaux = []
        for jour_cible, lignes in pd.Series(cible_index).groupby(cible_index.date):
            src = source_par_jour[appariement[jour_cible]]
            n = len(lignes)
            if len(src) < n:
                src = pd.concat([src] + [src.iloc[[-1]]] * (n - len(src)))
            bloc = src.iloc[:n].copy()
            bloc.index = pd.DatetimeIndex(lignes)
            morceaux.append(bloc)
        return pd.concat(morceaux).sort_index()

    cible = assembler(apparier_jours(an_source, an_cible))

    col = "temperature_normale_lissee_degc"
    if col in df.columns:
        clim = assembler(_appariement_calendaire(an_source, an_cible))
        cible[col] = clim[col]
        cible["temperature_realisee_lissee_degc"] = clim[col]
    return cible
