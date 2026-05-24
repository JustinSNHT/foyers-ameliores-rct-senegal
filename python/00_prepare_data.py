"""
00_prepare_data.py
==================
Pipeline de préparation des données — Projet RCT Foyers Améliorés.

Toutes les extractions sont vectorisées (pandas) pour gérer les fichiers
bruts à 13k-26k colonnes sans boucles row-by-row.

Étapes :
  1. Chargement + cache parquet des deux CSV bruts (lecture lente une fois)
  2. Nettoyage téléphones (junk, normalisation 221, dédoublonnage aléatoire)
  3. Panel inner join sur hh_id (hash téléphone)
  4. Identification vectorisée du slot de la femme ciblée (women_name_*)
  5. Extraction vectorisée des outcomes (Q1-Q4) dans les deux vagues
  6. Scores composites (attitude entrepreneuriale O, autonomisation actif)
  7. Dataset ANCOVA wide : Y_B + Y_E + traitement + stratification

Design RCT (3 bras, randomisation au niveau groupement) :
  T1 = Foyer amélioré + formation  |  β₁ = impact total
  T2 = Formation seule             |  β₂ = impact formation seule
  T3 = Contrôle                   |  β₁ − β₂ = impact marginal foyer
"""
import os, hashlib, warnings
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

warnings.filterwarnings('ignore')

# ============================================================================
# Config
# ============================================================================
ROOT = Path(__file__).resolve().parents[1]
RAW  = ROOT / 'data' / 'raw'
OUT  = ROOT / 'data' / 'processed'
SCR  = ROOT / 'data' / '_scratch'
OUT.mkdir(parents=True, exist_ok=True)
SCR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / '.env')
SALT = os.getenv('ANON_SALT', '')
if not SALT:
    raise RuntimeError('ANON_SALT manquant dans .env')

JUNK_PHONES   = {'888', '999', '777777777', '7777777777', '0', ''}
ERROR_CODES   = {-888, -999, 888, 999, 9999, 99, -777, 777}
MAX_WOMEN     = 24
MAX_OCCUP     = 60
MAX_ACTIF     = 12

def log(msg): print(f'[prep] {msg}')


# ============================================================================
# Helpers
# ============================================================================
def norm_phone(s):
    s = ''.join(c for c in str(s) if c.isdigit())
    if s.startswith('221') and len(s) == 12:
        s = s[3:]
    return s if len(s) >= 7 else None

def hash_id(phone):
    return hashlib.sha256(f'{SALT}|{phone}'.encode()).hexdigest()[:12]

def to_num(series):
    """Numérique + recode codes d'erreur → NaN."""
    return pd.to_numeric(series, errors='coerce').replace(
        {v: np.nan for v in ERROR_CODES}
    )

def find_file(pattern):
    matches = sorted(RAW.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f'Aucun fichier {pattern!r} dans {RAW}. '
            f'Fichiers : {[p.name for p in RAW.iterdir()]}'
        )
    return matches[0]


# ============================================================================
# Chargement avec cache parquet
# ============================================================================
def load_wave(pattern, label, force=False):
    cache = SCR / f'_cache_{label}.parquet'
    if cache.exists() and not force:
        log(f'Cache {label} trouvé — lecture parquet...')
        return pd.read_parquet(cache)
    path = find_file(pattern)
    log(f'Lecture {label} depuis CSV ({path.stat().st_size/1e6:.0f} Mo)...')
    df = pd.read_csv(path, low_memory=False)
    log(f'  {len(df)} × {df.shape[1]} — mise en cache...')
    df.to_parquet(cache, index=False)
    return df


# ============================================================================
# Nettoyage téléphones
# ============================================================================
def clean_phones(df, phone_col, seed=42):
    df = df.copy()
    df['_phone'] = df[phone_col].apply(norm_phone)
    df.loc[df['_phone'].isin(JUNK_PHONES) | df['_phone'].isna(), '_phone'] = None
    n0 = len(df)
    df = df.dropna(subset=['_phone'])
    log(f'  Junk supprimés : {n0 - len(df)}')
    df = df.sample(frac=1, random_state=seed).drop_duplicates('_phone', keep='first')
    log(f'  Après dédoublonnage : {len(df)}')
    df['hh_id'] = df['_phone'].apply(hash_id)
    return df.reset_index(drop=True)


# ============================================================================
# Identification vectorisée du slot de la femme ciblée
# ============================================================================
def find_slots(df, name_col, max_slots=MAX_WOMEN, slot_col_prefix='women_name'):
    """Pour chaque ménage, retourne le premier slot s où {prefix}_s ≈ name_col.

    Renvoie une Series (index = df.index) avec le numéro de slot ou NaN.
    """
    target = df[name_col].fillna('').astype(str).str.strip().str.upper()
    slot_result = pd.Series(np.nan, index=df.index, dtype=float)

    wn_cols = [f'{slot_col_prefix}_{s}' for s in range(1, max_slots + 1)
               if f'{slot_col_prefix}_{s}' in df.columns]
    wn_df = (df[wn_cols].fillna('')
                        .astype(str)
                        .apply(lambda col: col.str.strip().str.upper()))

    # Passe 1 : match exact
    for s, col in enumerate(wn_cols, start=1):
        match = (wn_df[col] == target) & slot_result.isna()
        slot_result = slot_result.where(~match, float(s))

    # Passe 2 : match sur premier prénom (fallback)
    target_first = target.str.split().str[0].fillna('')
    for s, col in enumerate(wn_cols, start=1):
        wn_first = wn_df[col].str.split().str[0].fillna('')
        match = (wn_first == target_first) & (wn_first != '') & slot_result.isna()
        slot_result = slot_result.where(~match, float(s))

    found = slot_result.notna().sum()
    log(f'  [{slot_col_prefix}] Slot trouvé : {found}/{len(df)} ({100*found/len(df):.1f}%)')
    return slot_result


# ============================================================================
# Extraction vectorisée par slot
# ============================================================================
def extract_at_slot(df, base_name, slots, max_slots=MAX_WOMEN):
    """Extrait df[base_name_X] pour chaque ligne selon slots[i] = X."""
    result = pd.Series(np.nan, index=df.index, dtype=float)
    for s in range(1, max_slots + 1):
        col = f'{base_name}_{s}'
        if col not in df.columns:
            continue
        mask = slots == float(s)
        if mask.any():
            result = result.where(~mask, to_num(df[col][mask]))
    return result


def sum_across_slots(df, base_name, max_slots, default=np.nan):
    """Somme df[base_name_1] + ... + df[base_name_n] (ignore NaN)."""
    cols = [f'{base_name}_{s}' for s in range(1, max_slots + 1)
            if f'{base_name}_{s}' in df.columns]
    if not cols:
        return pd.Series(default, index=df.index)
    return df[cols].apply(to_num).sum(axis=1, min_count=1)


# ============================================================================
# Extraction des outcomes par vague
# ============================================================================
def extract_outcomes(df, wave, name_col):
    """Extraction vectorisée de tous les outcomes pour une vague.

    Stratégie des slots (deux rosters à distinguer) :
    - Baseline : women_name_* = adultes-femmes (gain_roster) → actif ET occup
    - Endline  : women_name_* = tous membres preloadés → occup uniquement
                 nom_epouse_*  = adultes-femmes (genre-femme) → actif/autonomie
    """
    log(f'\nExtraction vague {wave}...')
    out = pd.DataFrame({'hh_id': df['hh_id']})

    # --- Slots selon vague ---
    if wave == 'B':
        # Baseline : women_name_* indexe les adultes-femmes → valide pour actif ET occup
        slots_actif = find_slots(df, name_col, slot_col_prefix='women_name')
        slots_occup = slots_actif
    else:
        # Endline  : women_name_* = tous membres → pour occup (occupation de tous membres)
        #            nom_epouse_*  = adultes-femmes → pour actif/autonomie
        slots_occup = find_slots(df, name_col, slot_col_prefix='women_name')
        nom_epouse_max = len([c for c in df.columns if c.startswith('nom_epouse_')])
        slots_actif = find_slots(df, name_col,
                                 max_slots=max(nom_epouse_max, 12),
                                 slot_col_prefix='nom_epouse')

    out['women_slot_occup'] = slots_occup
    out['women_slot_actif'] = slots_actif

    # ---- Q1 : Temps de travail ----
    for base, label in [('actif17', 'travail_total_h'),
                        ('actif18', 'taches_menage_h'),
                        ('actif19', 'travail_propre_compte_h')]:
        out[label] = extract_at_slot(df, base, slots_actif)
        # Moyenne sur toutes les femmes du ménage (robustesse)
        cols = [f'{base}_{s}' for s in range(1, MAX_ACTIF+1) if f'{base}_{s}' in df.columns]
        out[f'{label}_mean'] = df[cols].apply(to_num).mean(axis=1) if cols else np.nan

    # D53_1 : temps cuisson avec foyer (endline uniquement)
    if wave == 'E':
        for col, label in [('D51_1','foyer_prep_h'), ('D52_1','foyer_usage_h'),
                           ('D53_1','foyer_cuisson_h'), ('D44_1','foyer_frequence'),
                           ('D43_1','foyer_ameliore_principal')]:
            out[label] = to_num(df[col]) if col in df.columns else np.nan

    # ---- Q2 : Revenu ----
    out['revenu_femme']        = extract_at_slot(df, 'occup04', slots_occup, MAX_OCCUP)
    out['revenu_femme_annuel'] = extract_at_slot(df, 'occup10', slots_occup, MAX_OCCUP)
    out['revenu_menage']       = sum_across_slots(df, 'occup04', MAX_OCCUP)
    out['occup_statut']        = extract_at_slot(df, 'occup01', slots_occup, MAX_OCCUP)

    # ---- Q3 : Attitude entrepreneuriale (O1-O30) ----
    o_cols = [f'O{i}' for i in range(1, 31) if f'O{i}' in df.columns]
    o_df = df[o_cols].apply(to_num)
    for col in o_cols:
        out[col] = o_df[col]
    o9_cols  = [f'O{i}' for i in range(1,  10) if f'O{i}' in df.columns]
    o30_cols = [f'O{i}' for i in range(19, 31) if f'O{i}' in df.columns]
    out['score_entrepreneurial'] = o_df[o9_cols].mean(axis=1)   if o9_cols  else np.nan
    out['score_genre_attitudes'] = o_df[o30_cols].mean(axis=1)  if o30_cols else np.nan
    out['score_O_global']        = o_df.mean(axis=1)

    # ---- Q4 : Combustibles ----
    out['N6']  = df['N6']  if 'N6'  in df.columns else np.nan
    out['N17'] = to_num(df['N17']) if 'N17' in df.columns else np.nan
    for suffix, label in [('1','bois'),('2','fumier'),('3','charbon'),
                          ('4','gaz'),('5','petrole')]:
        col = f'D56.{suffix}'
        out[f'D56_{label}'] = to_num(df[col]) if col in df.columns else np.nan
    out['D6_collecte'] = to_num(df['D6']) if 'D6' in df.columns else np.nan

    # ---- Autonomisation (actif08-16, slot adultes-femmes) ----
    for i in range(8, 17):
        base = f'actif{i:02d}'
        out[f'auto_{i:02d}'] = extract_at_slot(df, base, slots_actif, MAX_ACTIF)
    auto_cols = [f'auto_{i:02d}' for i in range(8, 17)]
    out['score_autonomie'] = out[auto_cols].apply(to_num).mean(axis=1)

    # ---- Structure ménage ----
    out['taille_menage'] = to_num(df['member_roster_count']) \
        if 'member_roster_count' in df.columns else np.nan
    out['N13'] = df['N13'] if 'N13' in df.columns else np.nan

    log(f'  {out.shape[1]} variables extraites')
    return out


# ============================================================================
# Main
# ============================================================================
def main():
    log('=== PIPELINE RCT FOYERS AMÉLIORÉS ===')

    b = load_wave('*Baseline*', 'baseline')
    e = load_wave('*Endline*',  'endline')

    log('\nNettoyage téléphones — baseline :')
    b_c = clean_phones(b, 'tel_cible')
    log('Nettoyage téléphones — endline :')
    e_c = clean_phones(e, 'pull_tel_cible')

    log('\nConstruction du panel (inner join)...')
    panel = b_c[['hh_id','treatment','region','zone','village','codezone']].merge(
        e_c[['hh_id']],
        on='hh_id', how='inner'
    )
    log(f'  {len(panel)} ménages | attrition : {len(b_c)-len(panel)}')
    log('  ' + str(panel['treatment'].value_counts().to_dict()))

    # Restreindre les deux waves au panel
    b_panel = b_c[b_c['hh_id'].isin(panel['hh_id'])].reset_index(drop=True)
    e_panel = e_c[e_c['hh_id'].isin(panel['hh_id'])].reset_index(drop=True)

    # Extraction
    out_B = extract_outcomes(b_panel, 'B', 'household_name')
    out_E = extract_outcomes(e_panel, 'E', 'pull_household_name')

    # Suffixes _B / _E
    out_B = out_B.rename(columns={c: f'{c}_B' for c in out_B.columns if c != 'hh_id'})
    out_E = out_E.rename(columns={c: f'{c}_E' for c in out_E.columns if c != 'hh_id'})

    # Assemblage final
    final = (panel
             .merge(out_B, on='hh_id', how='left')
             .merge(out_E, on='hh_id', how='left')
             .drop_duplicates('hh_id')
             .reset_index(drop=True))

    # Dummies traitement
    final['T1'] = (final['treatment'] == 'T1').astype(int)
    final['T2'] = (final['treatment'] == 'T2').astype(int)

    # Sauvegarde
    out_path = OUT / 'panel_ancova.parquet'
    final.to_parquet(out_path, index=False)
    log(f'\n✓ {out_path.relative_to(ROOT)} : {len(final)} ménages × {final.shape[1]} variables')

    # Dictionnaire
    dico = [
        ('hh_id',                   'Identifiant ménage anonymisé',           'hash(tel_cible)'),
        ('treatment / T1 / T2',     'Bras de traitement (T1/T2/T3)',           'treatment'),
        ('region / zone',           'Région et zone agro-écologique (strate)', 'region, zone'),
        ('taille_menage_B',         'Taille du ménage',                        'member_roster_count'),
        ('taches_menage_h_B/_E',    'Tâches ménagères par jour (h) — femme',   'actif18_slot'),
        ('travail_propre_compte_h', 'Travail propre compte / jour (h)',         'actif19_slot'),
        ('foyer_cuisson_h_E',       'Temps cuisson foyer amélioré / jour',      'D53_1 endline'),
        ('foyer_frequence_E',       'Fréquence utilisation du foyer',            'D44_1 endline'),
        ('revenu_femme_B/_E',       'Revenu mensuel femme ciblée (FCFA)',        'occup04_slot'),
        ('revenu_menage_B/_E',      'Revenu mensuel total ménage (FCFA)',         'sum(occup04_*)'),
        ('score_O_global_B/_E',     'Score attitude entrepreneuriale (O1-O30)',  'mean(O1-O30)'),
        ('score_genre_attitudes',   'Score attitudes genre entrepreneuriat',      'mean(O19-O30)'),
        ('score_autonomie_B/_E',    'Score autonomisation (actif08-16)',           'mean(actif08-16)'),
        ('N6_B/_E',                 'Combustible principal cuisson',              'N6'),
        ('D56_charbon_B/_E',        'Valeur stock charbon (FCFA)',                'D56.3'),
        ('N17_B/_E',                "Échelle de bien-être (1-6)",                 'N17'),
    ]
    pd.DataFrame(dico, columns=['variable','label','source_brut']).to_csv(
        OUT / 'dictionnaire_variables.csv', index=False, encoding='utf-8')
    log('✓ dictionnaire_variables.csv')

    log('\n=== RÉSUMÉ ===')
    for arm in ['T1','T2','T3']:
        n = (final['treatment'] == arm).sum()
        log(f'  {arm} : {n} ménages')
    log(f'  Slot actif (baseline)   : {final["women_slot_actif_B"].notna().sum()}/{len(final)}')
    log(f'  Slot actif (endline)    : {final["women_slot_actif_E"].notna().sum()}/{len(final)}')
    log(f'  Score O global endline  : {final["score_O_global_E"].notna().sum()}')
    log(f'  Revenu femme (baseline) : {(final["revenu_femme_B"]>0).sum()}')
    log(f'  taches_menage_h_mean_E  : {final["taches_menage_h_mean_E"].notna().sum()} (moyenne ménage, recommandée)')
    log(f'  N17 endline (1-6)       : {final["N17_E"].notna().sum()} | moy={final["N17_E"].mean():.2f}')
    log('\n  Note ANCOVA : pour Q1, utiliser taches_menage_h_mean_B/_E (couverture complète)')
    log('  plutôt que taches_menage_h_B/_E (slot individuel, 94%/32% couverture).')


if __name__ == '__main__':
    main()
