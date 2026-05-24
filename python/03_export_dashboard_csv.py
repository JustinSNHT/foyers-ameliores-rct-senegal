"""
03_export_dashboard_csv.py
==========================
Export des résultats ANCOVA en CSV pour Power BI Desktop.
Encodage UTF-8 BOM, séparateur point-virgule, décimale virgule (locale française).

Sorties :
  powerbi/data/impact_estimates.csv     — 3 estimands × N outcomes avec labels
  powerbi/data/moyennes_par_bras.csv    — moyennes T1/T2/T3 par outcome endline
  powerbi/data/metadata.csv             — paramètres du projet

Usage : python python/03_export_dashboard_csv.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data' / 'processed'
PBI  = ROOT / 'powerbi' / 'data'
PBI.mkdir(parents=True, exist_ok=True)

CSV_KWARGS = dict(index=False, encoding='utf-8-sig', sep=';', decimal=',')

# ============================================================================
# Libellés
# ============================================================================
LABELS = {
    'Taches menageres / jour (h) — femme moy.' : 'Taches menageres / jour (h)',
    'Travail propre compte / jour (h)'          : 'Travail propre compte (h)',
    'Revenu total menage (FCFA/mois)'           : 'Revenu total menage (FCFA)',
    'Revenu femme ciblee (FCFA/mois)'           : 'Revenu femme ciblee (FCFA)',
    'Score O global (O1-O30)'                   : 'Score attitude O global',
    'Score motivation travail (O1-O9)'          : 'Score motivation travail',
    'Score attitudes genre (O19-O30)'           : 'Attitudes genre / entrepr.',
    'Stock charbon (FCFA)'                      : 'Stock charbon (FCFA)',
    'Stock bois (FCFA)'                         : 'Stock bois (FCFA)',
    'Echelle bien-etre (1-6)'                   : 'Echelle bien-etre (1-6)',
}

COMP_LABELS = {
    'T1 vs T3 (total)'    : 'T1 vs T3 - Foyer + formation',
    'T2 vs T3 (formation)': 'T2 vs T3 - Formation seule',
    'T1 vs T2 (foyer)'    : 'T1 vs T2 - Foyer seul (marginal)',
}

QUESTION_LABELS = {
    'Q1_Temps'       : 'Q1 - Temps de travail',
    'Q2_Revenu'      : 'Q2 - Revenu',
    'Q3_Attitude'    : 'Q3 - Attitude entrepreneuriale',
    'Q4_Combustibles': 'Q4 - Combustibles & Bien-etre',
}

# ============================================================================
# 1. impact_estimates.csv
# ============================================================================
est = pd.read_parquet(PROC / 'agg_impact_estimates.parquet')

est['label_outcome']     = est['outcome'].map(LABELS).fillna(est['outcome'])
est['label_comparaison'] = est['comparaison'].map(COMP_LABELS).fillna(est['comparaison'])
est['label_question']    = est['question'].map(QUESTION_LABELS).fillna(est['question'])

est['direction'] = np.where(
    est['significatif'] == 0, 'Non sig.',
    np.where(est['coef'] > 0, 'Positif sig.', 'Negatif sig.')
)
est['pval_formatted'] = est['pval'].apply(
    lambda p: '< 0.001' if p < 0.001 else f'{p:.3f}'
)
est['effet_pct_ctrl'] = (
    est['coef'] / est['mean_T3'].replace(0, np.nan) * 100
).round(1)

cols = ['label_question', 'label_outcome', 'label_comparaison',
        'question', 'outcome', 'comparaison',
        'n', 'mean_T3', 'coef', 'se', 'lo95', 'hi95',
        'pval', 'pval_formatted', 'effet_std', 'effet_pct_ctrl',
        'significatif', 'direction']
est[[c for c in cols if c in est.columns]].to_csv(
    PBI / 'impact_estimates.csv', **CSV_KWARGS)
print(f"impact_estimates.csv — {len(est)} lignes "
      f"({est['outcome'].nunique()} outcomes x 3 estimands)")

# ============================================================================
# 2. moyennes_par_bras.csv
# ============================================================================
panel = pd.read_parquet(PROC / 'panel_ancova.parquet')

primary = {
    'taches_menage_h_mean_E' : 'Taches menageres / jour (h)',
    'revenu_menage_E'        : 'Revenu total menage (FCFA)',
    'score_O_global_E'       : 'Score O global',
    'score_genre_attitudes_E': 'Attitudes genre / entrepr.',
    'D56_charbon_E'          : 'Stock charbon (FCFA)',
    'N17_E'                  : 'Echelle bien-etre (1-6)',
}

rows = []
for col, label in primary.items():
    if col not in panel.columns:
        continue
    for arm in ['T1', 'T2', 'T3']:
        sub = panel.loc[panel['treatment'] == arm, col].dropna()
        rows.append({
            'outcome'      : col,
            'label_outcome': label,
            'bras'         : arm,
            'n'            : len(sub),
            'moyenne'      : round(sub.mean(), 4),
            'ecart_type'   : round(sub.std(),  4),
            'mediane'      : round(sub.median(), 4),
        })

pd.DataFrame(rows).to_csv(PBI / 'moyennes_par_bras.csv', **CSV_KWARGS)
print(f"moyennes_par_bras.csv — {len(rows)} lignes")

# ============================================================================
# 3. metadata.csv
# ============================================================================
meta = pd.DataFrame([
    ('projet',       'RCT Foyers Ameliores - Senegal rural'),
    ('T1',           'Foyer ameliore + formation (n=614)'),
    ('T2',           'Formation seule (n=616)'),
    ('T3',           'Controle (n=620)'),
    ('n_panel',      '1850'),
    ('randomisation','Niveau groupement (village)'),
    ('strates',      '5 zones agro-ecologiques'),
    ('estimateur',   'ANCOVA - feols + cluster SE village'),
    ('logiciel',     'Python 3.12 + R fixest'),
    ('mise_a_jour',  pd.Timestamp.today().strftime('%d/%m/%Y')),
], columns=['cle', 'valeur'])
meta.to_csv(PBI / 'metadata.csv', **CSV_KWARGS)
print(f"metadata.csv — {len(meta)} entrees")

print(f"\nFichiers dans : {PBI}")
print("Power BI : separateur = point-virgule | decimale = virgule")
