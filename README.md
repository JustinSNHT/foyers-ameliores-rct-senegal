# RCT Foyers Améliorés — Rural Senegal

Randomised controlled trial evaluating the impact of improved cookstoves on women's domestic workload, income, entrepreneurial attitudes, and fuel use in rural Senegal. The programme distributed improved cookstoves alongside an entrepreneurship and management training to female members of women's groups (*groupements de femmes*), allowing a three-arm design that cleanly separates the effects of the stove from the effects of the training. This repository contains the full analysis pipeline — data preparation, ANCOVA estimation in Python and R, and a Power BI dashboard.

## Design and data

Random assignment was at the *groupement* level (375 villages), stratified by agroecological zone. Households were allocated in equal thirds to three arms:

- **T1** — improved cookstove plus entrepreneurship and management training (614 households in the cleaned panel)
- **T2** — training only (616 households)
- **T3** — control, no intervention (620 households)

A baseline survey was conducted in June 2023, with an endline following programme implementation. The panel was constructed by matching households across waves on normalised mobile phone numbers after removing invalid entries (codes 888, 999, 777777777) and randomly resolving synchronisation duplicates. The final analysis sample comprises **1 850 households** — one baseline household could not be matched at endline, representing an attrition rate of 0.05 per cent with no differential pattern by arm.

The balance check on baseline characteristics (household size, workload, income, entrepreneurial attitude score, wellbeing) shows no statistically significant differences across the three arms at the 5 per cent level, consistent with a well-executed cluster randomisation.

## Findings

The three-arm design produces three estimands per outcome: β₁ (T1 versus T3, the combined effect of stove and training), β₂ (T2 versus T3, the training effect alone), and β₁ − β₂ (the marginal effect of the stove, conditional on training). Results are from the ANCOVA specification with baseline outcome controls, zone fixed effects, and village-clustered standard errors.

**Domestic workload — the clearest pathway.** Both treatment arms reduce the time adult women in treated households spend on domestic tasks. Relative to the control group, T1 households report 0.79 fewer hours of household work per day (p < 0.001) and T2 households report 0.48 fewer hours (p = 0.010). The marginal effect of the stove — β₁ − β₂ = −0.30 hours per day — is marginally significant (p = 0.088). This ordering is informative: training alone accounts for roughly 60 per cent of the time savings. The stove adds a further reduction, but the dominant mechanism runs through the training, not the equipment.

**Entrepreneurial attitude.** The training significantly improves women's work motivation (O1–O9 sub-score) in both T1 (β₁ = +0.067, p = 0.003) and T2 (β₂ = +0.043, p = 0.050), with no significant difference between them. On the gender attitudes toward entrepreneurship dimension (O19–O30), however, the stove has an effect that the training alone does not: β₁ − β₂ = +0.135 (p = 0.002). Households that received the stove — and thus experienced the concrete time savings it generates — show more favourable attitudes toward women's participation in business. This is consistent with a mechanism in which changed daily practices, rather than instruction alone, shift gendered beliefs about economic roles.

**Fuel use.** T2 households reduce their charcoal stock by approximately 531 FCFA relative to control (p = 0.026), suggesting that training on efficient cooking practices changes household fuel management even without the stove. The T1 coefficient moves in the opposite direction relative to T2 (β₁ − β₂ = +330, p = 0.055), plausibly because improved cookstoves in this context are charcoal-based — households receiving the stove maintain a larger charcoal stock to operate it.

**Income.** Treated households show positive but imprecise income effects. The T1 point estimate for total household income is +14 868 FCFA per month (approximately 6 per cent of the control group mean), but the standard error is large (p = 0.20). The endline falls too soon after programme implementation to capture income effects that likely materialise over longer horizons as women invest freed time in productive activities.

## Methodology

The analysis uses an ANCOVA specification for each outcome:

*Y*₍endline₎ = α + β₁·T1 + β₂·T2 + γ·*Y*₍baseline₎ + δ·zone + ε

Controlling the lagged baseline value of each outcome improves precision without changing consistency, since random assignment ensures orthogonality between treatment and potential outcomes. Zone fixed effects absorb between-stratum variation. Standard errors are clustered at the village level. The strates *CENTRE NORD* and *CENTRE OUEST* are merged in estimation: the two zones belong to the same randomisation stratum but were recorded under different labels, producing a spurious imbalance that would otherwise cause multicollinearity in the zone fixed effects.

The marginal effect of the stove, β₁ − β₂, is tested via a Wald test using the full variance-covariance matrix of the clustered estimator. The Python and R implementations produce consistent estimates, as verified by the cross-validation figure in `docs/figures/validation_python_R.png`.

All estimates are intent-to-treat: they measure the effect of assignment to a treatment arm, not of actual stove adoption or training attendance.

## Repository structure

```
foyers-ameliores-rct-senegal/
├── data/
│   ├── raw/              ← survey CSVs, gitignored (PII)
│   ├── processed/        ← aggregated outputs committed here
│   └── _scratch/         ← parquet cache, gitignored
├── python/
│   ├── 00_prepare_data.py   ← phone cleaning, panel, outcome extraction
│   ├── 01_eda.ipynb         ← balance check, attrition, completeness
│   ├── 02_analysis.ipynb    ← ANCOVA 3 bras, forest plot
│   └── 03_export_dashboard_csv.py
├── r/
│   ├── install_packages.R
│   ├── 01_analysis.R        ← fixest::feols + modelsummary table
│   └── 02_figures.R         ← forest plot, Python ↔ R cross-validation
├── powerbi/
│   ├── data/                ← CSV exports (UTF-8 BOM, semicolon)
│   ├── screenshots/
│   └── GUIDE_CONSTRUCTION.md
└── docs/
    ├── 01_framing.md
    └── figures/
```

## Reproducing the analysis

```bash
# 1. Environment
cd foyers-ameliores-rct-senegal
python -m venv .venv && source .venv/Scripts/activate
pip install -r python/requirements.txt
python -m ipykernel install --user \
       --name=foyers-ameliores-rct-senegal \
       --display-name="Python (Foyers RCT)"

# 2. Anonymisation salt
echo 'ANON_SALT=your-salt-here' > .env

# 3. Run pipeline
python python/00_prepare_data.py
jupyter notebook python/01_eda.ipynb
jupyter notebook python/02_analysis.ipynb
python python/03_export_dashboard_csv.py

# 4. R replication
Rscript r/install_packages.R
Rscript r/01_analysis.R
Rscript r/02_figures.R
```

Raw survey files are not versioned (PII: phones, household head names). The preparation script caches both CSVs as parquet on first run. The processed panel (`panel_ancova.parquet`) is also not committed — household-level data across identifiable rural communities carries re-identification risk even after phone hashing. Committed outputs are aggregates only.

## Limitations

**Intent-to-treat with unknown compliance.** The estimates measure the effect of assignment, not of actual stove use or training attendance. If stove adoption was incomplete in T1, the ITT estimate is a lower bound on the effect among users.

**Single endline, short follow-up.** Income effects from reinvested time are unlikely to be detectable within the survey's time horizon. The null income result should not be read as evidence against a long-run effect; a follow-up at twelve to twenty-four months post-endline would be needed.

**Possible within-village spillovers.** T1, T2, and T3 households coexist within the same villages in some strata. Knowledge or practice diffusion from treated to control households would compress the estimated effects downward.

**Workload measure.** The primary time-use outcome is the household-level average across all adult women, not the targeted woman specifically. This results from a roster index misalignment in the wide-format SurveyCTO export: the preloaded household member index at endline does not align with the adult-women activity-diary index. The household average is a valid programme-level measure but limits individual-level heterogeneity analysis.

**Agroecological heterogeneity.** The programme spans five zones with markedly different livelihood systems and fuel markets. Point estimates represent averages across contexts where mechanisms may operate differently; the analysis notebook provides zone-stratified estimates, though these are underpowered at the zone level.

## Author

**Justin Chery** — Associate Researcher & Evaluation Specialist, Centre de Recherche sur le Développement Économique et Social (CRDES), Dakar, Senegal. PhD candidate in Economics, Université Gaston Berger.

[GitHub](https://github.com/JustinSNHT)

## Licence

Survey data: not redistributed (property of CRDES; contact the author for access queries).
