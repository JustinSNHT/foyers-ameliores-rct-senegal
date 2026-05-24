# install_packages.R — RCT Foyers Améliorés
packages <- c(
  "tidyverse",      # dplyr, ggplot2, purrr
  "arrow",          # lecture parquet
  "fixest",         # feols : ANCOVA + cluster SE, très rapide
  "modelsummary",   # tables de régression publication-ready
  "car",            # linearHypothesis (test b1-b2)
  "broom",          # tidy() sur les modèles
  "patchwork",      # composition de plots
  "scales"          # formatage axes
)

new <- packages[!packages %in% installed.packages()[,"Package"]]
if (length(new)) install.packages(new, repos = "https://cloud.r-project.org")
for (p in packages) cat(sprintf("  [%s] %s\n",
  ifelse(requireNamespace(p, quietly = TRUE), "OK", "MANQUANT"), p))
