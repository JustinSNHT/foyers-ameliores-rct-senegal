# 02_figures.R
# =============================================================================
# Figures Phase 2.5 — RCT Foyers Améliorés :
#   - Forest plot des 3 estimands (b1, b2, b1-b2) par outcome
#   - Validation croisée Python ↔ R (nuage de points b1)
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(patchwork)
  library(scales)
  library(arrow)
})

ROOT <- "C:/Users/DELL/OneDrive/Documents/portfolio-raw-data/Foyer_amélioré/foyers-ameliores-rct-senegal"
PROC <- file.path(ROOT, "data", "processed")
FIG  <- file.path(ROOT, "docs", "figures")
dir.create(FIG, showWarnings = FALSE, recursive = TRUE)

objs    <- readRDS(file.path(PROC, "_R_objects_rct.rds"))
res_df  <- objs$summary

# =============================================================================
# 1. Forest plot — effets standardisés, 3 estimands
# =============================================================================
# =============================================================================
# 1. Forest plot — effets standardisés, 3 estimands
# =============================================================================

# Extraire sd_ctrl depuis la liste de résultats pour chaque outcome
sd_lookup <- map_dfr(names(objs$results), function(lab) {
  tibble(outcome  = lab,
         sd_ctrl  = objs$results[[lab]]$meta$sd_ctrl)
})

# Calculer les IC standardisés par join
plot_df <- res_df %>%
  left_join(sd_lookup, by = "outcome") %>%
  filter(!is.na(effet_std), !is.na(sd_ctrl), sd_ctrl > 0) %>%
  mutate(
    lo_std     = lo95 / sd_ctrl,
    hi_std     = hi95 / sd_ctrl,
    comp_label = case_when(
      comparaison == "T1_vs_T3" ~ "T1 vs T3 (total)",
      comparaison == "T2_vs_T3" ~ "T2 vs T3 (formation)",
      comparaison == "T1_vs_T2" ~ "T1 vs T2 (foyer seul)"
    ),
    comp_label = factor(comp_label,
                        levels = c("T1 vs T3 (total)",
                                   "T2 vs T3 (formation)",
                                   "T1 vs T2 (foyer seul)"))
  )

COLORS <- c(
  "T1 vs T3 (total)"       = "#d62728",
  "T2 vs T3 (formation)"   = "#1f77b4",
  "T1 vs T2 (foyer seul)"  = "#2ca02c"
)

p_forest <- ggplot(plot_df,
                   aes(x = effet_std, y = outcome,
                       color = comp_label,
                       xmin = lo_std, xmax = hi_std,
                       group = comp_label)) +
  geom_vline(xintercept = 0, color = "black", linewidth = 0.4) +
  geom_vline(xintercept = c(-0.2, 0.2),
             color = "grey60", linetype = "dashed", linewidth = 0.3) +
  geom_errorbarh(height = 0, alpha = 0.5, linewidth = 0.7,
                 position = position_dodge(width = 0.5)) +
  geom_point(size = 2.5, position = position_dodge(width = 0.5)) +
  scale_color_manual(values = COLORS) +
  scale_x_continuous(labels = label_number(accuracy = 0.1)) +
  labs(
    x = "Effet standardise (b / SD controle) — IC 95%",
    y = NULL,
    color = NULL,
    title = "Impact du projet foyers ameliores — ANCOVA 3 bras",
    subtitle = "Rouge = T1 (foyer+form.) | Bleu = T2 (form. seule) | Vert = marginal foyer"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    legend.position = "bottom",
    plot.title    = element_text(face = "bold"),
    plot.subtitle = element_text(color = "grey40", size = 9)
  )

ggsave(file.path(FIG, "forest_plot_ancova_R.png"),
       p_forest, width = 10, height = 7, dpi = 150)
cat("✓ docs/figures/forest_plot_ancova_R.png\n")

# =============================================================================
# 2. Validation croisée Python ↔ R
# =============================================================================
py_path <- file.path(PROC, "agg_impact_estimates.parquet")
if (file.exists(py_path)) {
  py_est <- read_parquet(py_path) %>%
    filter(comparaison == "T1 vs T3 (total)") %>%
    select(outcome, coef_py = coef)
  
  comp <- res_df %>%
    filter(comparaison == "T1_vs_T3") %>%
    select(outcome, coef_R = coef) %>%
    inner_join(py_est, by = "outcome")
  
  if (nrow(comp) > 0) {
    p_comp <- ggplot(comp, aes(x = coef_py, y = coef_R, label = outcome)) +
      geom_abline(slope = 1, intercept = 0, color = "grey50", linetype = "dashed") +
      geom_point(size = 2.5, color = "#1f77b4") +
      geom_text(size = 2.5, vjust = -0.7, color = "grey40") +
      labs(
        x = "b1 Python (HC3 clustere)",
        y = "b1 R (feols cluster SE)",
        title = "Validation croisee Python <-> R",
        subtitle = "b1 = T1 vs T3 — diagonale = replique parfaite"
      ) +
      theme_minimal(base_size = 11) +
      theme(plot.title = element_text(face = "bold"))
    
    ggsave(file.path(FIG, "validation_python_R.png"),
           p_comp, width = 7, height = 6, dpi = 150)
    cat("✓ docs/figures/validation_python_R.png\n")
  }
}

cat("\n=== FIN 02_figures.R ===\n")