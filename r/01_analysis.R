# 01_analysis.R
# =============================================================================
# Réplication R de la Phase 2.4 — RCT Foyers Améliorés.
#
# Spécification ANCOVA (3 bras) :
#   Y_E ~ T1 + T2 + Y_B | strate   (fixest::feols, effets fixes absorbés)
#
# SE clustérisés au niveau village.
# Trois estimands : b1 (T1 vs T3), b2 (T2 vs T3), b1-b2 (foyer marginal).
# =============================================================================

suppressPackageStartupMessages({
  library(arrow)
  library(tidyverse)
  library(fixest)
  library(modelsummary)
  library(broom)
})

# =============================================================================
# Chemins — adapter ROOT si changement de machine
# =============================================================================
ROOT <- "C:/Users/DELL/OneDrive/Documents/portfolio-raw-data/Foyer_amélioré/foyers-ameliores-rct-senegal"
PROC <- file.path(ROOT, "data", "processed")
FIG  <- file.path(ROOT, "docs", "figures")
dir.create(FIG, showWarnings = FALSE, recursive = TRUE)

# =============================================================================
# 1. Données
# =============================================================================
panel <- read_parquet(file.path(PROC, "panel_ancova.parquet"))
cat("Panel :", nrow(panel), "menages x", ncol(panel), "variables\n")

# Fusion strates CENTRE NORD + CENTRE OUEST
panel <- panel %>%
  mutate(
    strate = case_when(
      zone %in% c("CENTRE NORD", "CENTRE OUEST") ~ "CENTRE",
      TRUE ~ zone
    ),
    strate = factor(strate),
    T1     = as.integer(treatment == "T1"),
    T2     = as.integer(treatment == "T2")
  )

cat("\nStrates apres fusion :\n")
print(table(panel$strate, panel$treatment))

# =============================================================================
# 2. Fonction ANCOVA (fixest::feols)
# =============================================================================
run_ancova <- function(Y_E, Y_B = NULL, data = panel) {
  cols <- c("T1", "T2", "strate", "village", Y_E)
  if (!is.null(Y_B) && Y_B %in% names(data)) cols <- c(cols, Y_B)
  sub <- data %>% select(all_of(unique(cols))) %>% drop_na()
  if (nrow(sub) < 100) return(NULL)

  # feols avec effets fixes de strate absorbés (|strate) et SE clustérisés
  if (!is.null(Y_B) && Y_B %in% names(sub)) {
    fmla <- as.formula(paste0(Y_E, " ~ T1 + T2 + ", Y_B, " | strate"))
  } else {
    fmla <- as.formula(paste0(Y_E, " ~ T1 + T2 | strate"))
  }
  m <- feols(fmla, data = sub, cluster = ~village, warn = FALSE)

  # Extraction coefficients + SE clustérisés
  co <- coef(m)
  vc <- vcov(m)
  se <- sqrt(diag(vc))

  ext <- function(nm) {
    b  <- co[nm]; s <- se[nm]
    pv <- 2 * pt(abs(b/s), df = degrees_freedom(m, "t"), lower.tail = FALSE)
    list(coef = b, se = s, pval = pv,
         lo = b - 1.96*s, hi = b + 1.96*s)
  }

  b1   <- ext("T1")
  b2   <- ext("T2")

  # b1 - b2 : test de Wald via la variance-covariance
  diff_est <- co["T1"] - co["T2"]
  var_diff  <- vc["T1","T1"] + vc["T2","T2"] - 2*vc["T1","T2"]
  se_diff   <- sqrt(max(var_diff, 0))
  pv_diff   <- 2 * pt(abs(diff_est/se_diff),
                       df = degrees_freedom(m, "t"), lower.tail = FALSE)

  b_diff <- list(coef = diff_est, se = se_diff, pval = pv_diff,
                 lo = diff_est - 1.96*se_diff,
                 hi = diff_est + 1.96*se_diff)

  ctrl    <- sub[sub$T1 == 0 & sub$T2 == 0, Y_E, drop = TRUE]
  sd_ctrl <- sd(ctrl, na.rm = TRUE)

  list(model    = m,
       T1_vs_T3 = b1,
       T2_vs_T3 = b2,
       T1_vs_T2 = b_diff,
       meta     = list(n = nrow(sub),
                       mean_T3 = mean(ctrl, na.rm = TRUE),
                       sd_ctrl = sd_ctrl,
                       Y_E = Y_E, Y_B = Y_B))
}

# Etiquette de significativité
sig_stars <- function(p) {
  if (is.na(p)) return("")
  if (p < 0.001) "***" else if (p < 0.01) "**" else
  if (p < 0.05)  "*"   else if (p < 0.10) "†"  else ""
}

# =============================================================================
# 3. Estimation par question analytique
# =============================================================================
outcomes_list <- list(
  Q1_Temps = list(
    c("taches_menage_h_mean_E",       "taches_menage_h_mean_B",
      "Taches menageres / j (h)"),
    c("travail_propre_compte_h_mean_E","travail_propre_compte_h_mean_B",
      "Travail propre compte (h)")
  ),
  Q2_Revenu = list(
    c("revenu_menage_E",  "revenu_menage_B",  "Revenu menage (FCFA/mois)"),
    c("revenu_femme_E",   "revenu_femme_B",   "Revenu femme ciblee (FCFA)")
  ),
  Q3_Attitude = list(
    c("score_O_global_E",        "score_O_global_B",        "Score O global (O1-O30)"),
    c("score_entrepreneurial_E", "score_entrepreneurial_B", "Score motivation O1-O9"),
    c("score_genre_attitudes_E", "score_genre_attitudes_B", "Score attitudes genre O19-O30")
  ),
  Q4_Combustibles = list(
    c("D56_charbon_E", "D56_charbon_B", "Stock charbon (FCFA)"),
    c("D56_bois_E",    "D56_bois_B",    "Stock bois (FCFA)"),
    c("N17_E",         "N17_B",         "Bien-etre (1-6)")
  )
)

all_results <- list()

for (q in names(outcomes_list)) {
  cat("\n===", q, "===\n")
  for (spec in outcomes_list[[q]]) {
    Y_E <- spec[1]; Y_B <- spec[2]; label <- spec[3]
    if (!Y_E %in% names(panel)) { cat(" Absent:", Y_E, "\n"); next }

    r <- run_ancova(Y_E, Y_B)
    if (is.null(r)) { cat(" Trop peu obs:", Y_E, "\n"); next }

    all_results[[label]] <- r
    d <- r$meta

    cat(sprintf("  %-38s  n=%d  moy.T3=%.3f\n", label, d$n, d$mean_T3))
    for (nm in c("T1_vs_T3","T2_vs_T3","T1_vs_T2")) {
      e   <- r[[nm]]
      lbl <- switch(nm, T1_vs_T3="b1", T2_vs_T3="b2", T1_vs_T2="b1-b2")
      cat(sprintf("    %6s : %+.4f  SE=%.4f  p=%.3f%s\n",
                  lbl, e$coef, e$se, e$pval, sig_stars(e$pval)))
    }
  }
}

# =============================================================================
# 4. Table de régression modelsummary (outcomes primaires)
# =============================================================================
cat("\n=== Table modelsummary ===\n")

primary <- c(
  "Taches men. (h)"  = "taches_menage_h_mean_E",
  "Revenu menage"    = "revenu_menage_E",
  "Score O global"   = "score_O_global_E",
  "Att. genre"       = "score_genre_attitudes_E",
  "Charbon (FCFA)"   = "D56_charbon_E",
  "Bien-etre (1-6)"  = "N17_E"
)

models_list <- lapply(names(primary), function(lbl) {
  Y_E <- primary[[lbl]]
  if (!Y_E %in% names(panel)) return(NULL)
  Y_B <- sub("_E$", "_B", Y_E)
  r <- run_ancova(Y_E, Y_B)
  if (!is.null(r)) r$model else NULL
})
names(models_list) <- names(primary)
models_list <- Filter(Negate(is.null), models_list)

tbl <- modelsummary(
  models_list,
  coef_map  = c("T1" = "T1 (foyer + formation)",
                "T2" = "T2 (formation seule)"),
  statistic = "({std.error})",
  stars     = c("†" = 0.10, "*" = 0.05, "**" = 0.01, "***" = 0.001),
  gof_omit  = "IC|Log|F|RMSE|Adj|Within|Pseudo",
  output    = "dataframe"
)
print(tbl)
write.csv(tbl, file.path(PROC, "agg_modelsummary_R.csv"), row.names = FALSE)
cat("Sauvegarde : agg_modelsummary_R.csv\n")

# =============================================================================
# 5. Export agrégats (comparaison croisée Python ↔ R)
# =============================================================================
rows_export <- map_dfr(names(all_results), function(label) {
  r <- all_results[[label]]
  d <- r$meta
  map_dfr(c("T1_vs_T3","T2_vs_T3","T1_vs_T2"), function(nm) {
    e <- r[[nm]]
    tibble(
      outcome     = label,
      comparaison = nm,
      coef        = e$coef, se = e$se,
      pval        = e$pval, lo95 = e$lo, hi95 = e$hi,
      effet_std   = ifelse(d$sd_ctrl > 0, e$coef / d$sd_ctrl, NA_real_),
      n = d$n, mean_T3 = d$mean_T3,
      significatif = as.integer(e$pval < 0.05)
    )
  })
})

write_parquet(rows_export, file.path(PROC, "agg_impact_estimates_R.parquet"))
cat("\nagg_impact_estimates_R.parquet :", nrow(rows_export), "lignes\n")

saveRDS(list(results = all_results, summary = rows_export),
        file.path(PROC, "_R_objects_rct.rds"))

cat("\n=== FIN 01_analysis.R ===\n")
cat("Suite : Rscript r/02_figures.R\n")
