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
    """Dimanche de Paques par l'algorithme de Meeus/Jones/Butcher.

    Trois feries francais sur onze en dependent (lundi de Paques, Ascension,
    lundi de Pentecote). Les lettres sont celles de l'algorithme publie : les
    renommer ne les rendrait pas plus parlantes. Verification : 2027 -> 28 mars.
    """
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
    """Les onze feries francais : huit a date fixe, trois cales sur Paques."""
    p = _paques(annee)
    return {dt.date(annee, 1, 1),            # jour de l'an
            p + dt.timedelta(days=1),        # lundi de Paques
            dt.date(annee, 5, 1),            # fete du travail
            dt.date(annee, 5, 8),            # victoire 1945
            p + dt.timedelta(days=39),       # Ascension
            p + dt.timedelta(days=50),       # lundi de Pentecote
            dt.date(annee, 7, 14), dt.date(annee, 8, 15), dt.date(annee, 11, 1),
            dt.date(annee, 11, 11), dt.date(annee, 12, 25)}


def _type_jour(d, feries):
    """Sept types : lundi=0 a dimanche=6, et 7 pour un ferie.

    Un ferie n'est pas un jour de semaine ordinaire : on y consomme comme un
    dimanche, pas comme le mardi qu'il est au calendrier. D'ou le 7e type, qui
    prime sur le jour de la semaine.
    """
    return 7 if d in feries else d.weekday()


def apparier_jours(an_source, an_cible):
    """A chaque jour de l'annee cible, le jour de MEME TYPE le plus proche dans
    l'annee source.

    Le 1er janvier 2027 est un vendredi ferie ; on ne peut pas lui donner le
    profil du 1er janvier 2025, qui tombait un mercredi ordinaire. On cherche
    donc un ferie de l'annee source, et parmi eux le plus proche dans la saison.
    """
    f_src, f_cib = jours_feries(an_source), jours_feries(an_cible)
    src = pd.date_range(f"{an_source}-01-01", f"{an_source}-12-31", freq="D").date
    cib = pd.date_range(f"{an_cible}-01-01", f"{an_cible}-12-31", freq="D").date

    # Ranger les jours sources par type, une fois pour toutes.
    par_type = {}
    for d in src:
        par_type.setdefault(_type_jour(d, f_src), []).append(d)

    appariement = {}
    for d in cib:
        # Repli sur le dimanche (type 6) si l'annee source n'a aucun jour de ce
        # type - cas theorique, mais une annee sans ferie planterait sinon.
        candidats = par_type.get(_type_jour(d, f_cib)) or par_type[6]
        ref = d.timetuple().tm_yday
        # Distance CIRCULAIRE : le 31 decembre est a 1 jour du 1er janvier, pas
        # a 364. Sans ca, les jours de fin d'annee iraient chercher un profil de
        # fevrier, et on perdrait la saison - le chauffage, donc l'essentiel.
        appariement[d] = min(candidats, key=lambda s: min(
            abs(s.timetuple().tm_yday - ref), 365 - abs(s.timetuple().tm_yday - ref)))
    return appariement


def _appariement_calendaire(an_source, an_cible):
    """Appariement par DATE et non par type : le 5 mars avec le 5 mars.

    La temperature normale est une climatologie : elle depend de la saison, pas
    du jour de la semaine. Lui appliquer l'appariement par type la decalerait de
    plusieurs jours sans raison. Le 29 fevrier se rabat sur le 28.
    """
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
    """Rejoue une annee source sur le calendrier de l'annee cible."""
    an_source = df.index[0].year
    pas = df.index[1] - df.index[0]     # 15 min ou 30 min, deduit des donnees
    cible_index = pd.date_range(f"{an_cible}-01-01", f"{an_cible}-12-31 23:59", freq=pas, tz=tz)
    source_par_jour = {j: g for j, g in df.groupby(df.index.date)}

    def assembler(appariement):
        """Colle bout a bout les journees sources, dans l'ordre de l'annee cible."""
        morceaux = []
        for jour_cible, lignes in pd.Series(cible_index).groupby(cible_index.date):
            src = source_par_jour[appariement[jour_cible]]
            n = len(lignes)
            # Les jours de changement d'heure n'ont pas 24 h : 23 en mars, 25 en
            # octobre. Si le jour source est plus court que le jour cible, on
            # repete sa derniere valeur ; s'il est plus long, on tronque.
            if len(src) < n:
                src = pd.concat([src] + [src.iloc[[-1]]] * (n - len(src)))
            bloc = src.iloc[:n].copy()
            bloc.index = pd.DatetimeIndex(lignes)     # redater sur l'annee cible
            morceaux.append(bloc)
        return pd.concat(morceaux).sort_index()

    cible = assembler(apparier_jours(an_source, an_cible))

    # DEUX appariements, pas un : la consommation suit le type de jour, la
    # temperature suit la saison. On repasse donc les colonnes de temperature
    # par l'appariement calendaire. Realisee = normale ici : par defaut, on
    # projette une annee a temperature NORMALE ; les scenarios y injecteront
    # ensuite une vraie annee meteo.
    col = "temperature_normale_lissee_degc"
    if col in df.columns:
        clim = assembler(_appariement_calendaire(an_source, an_cible))
        cible[col] = clim[col]
        cible["temperature_realisee_lissee_degc"] = clim[col]
    return cible
