# Guide de construction du dashboard Power BI — RCT Foyers Améliorés

## Vue d'ensemble

**Fichier à créer** : `powerbi/RCT_Foyers.pbix`
**Sources** : 3 CSV dans `powerbi/data/`
**Pages** : 4 pages thématiques
**Audience** : Bailleur et équipe programme

---

## Étape 0 — Prérequis

1. Lancer `python python/03_export_dashboard_csv.py`
2. Copier `docs/figures/forest_plot_ancova_R.png` → `powerbi/screenshots/`
3. Ouvrir Power BI Desktop

---

## Étape 1 — Import des 3 tables

**Accueil → Obtenir des données → Texte/CSV**

| Table | Fichier |
|---|---|
| `impact_estimates` | `powerbi/data/impact_estimates.csv` |
| `moyennes_par_bras` | `powerbi/data/moyennes_par_bras.csv` |
| `metadata` | `powerbi/data/metadata.csv` |

Séparateur : **Point-virgule** — si des colonnes numériques apparaissent en texte : clic droit sur l'en-tête → Modifier le type → Utiliser les paramètres régionaux → Anglais (États-Unis).

---

## Étape 2 — Modèle de données

Les 3 tables sont indépendantes — aucune relation à créer.

---

## Étape 3 — Mesures DAX

Sélectionner la table `impact_estimates` → **Nouvelle mesure** :

```dax
Nb_Sig =
COUNTROWS(FILTER(impact_estimates, impact_estimates[significatif] = 1))

Nb_Sig_T1 =
CALCULATE([Nb_Sig],
  impact_estimates[comparaison] = "T1 vs T3 (total)")

Nb_Sig_Foyer =
CALCULATE([Nb_Sig],
  impact_estimates[comparaison] = "T1 vs T2 (foyer)")

Effet_IC =
VAR b  = SELECTEDVALUE(impact_estimates[coef])
VAR lo = SELECTEDVALUE(impact_estimates[lo95])
VAR hi = SELECTEDVALUE(impact_estimates[hi95])
RETURN FORMAT(b, "+0.000;-0.000;0.000") &
       " [" & FORMAT(lo, "0.000") & "; " & FORMAT(hi, "0.000") & "]"

Couleur_Barre =
SWITCH(
    SELECTEDVALUE(impact_estimates[direction]),
    "Positif sig.", "#2ca02c",
    "Negatif sig.", "#d62728",
    "#aec7e8"
)
```

---

## Étape 4 — Thème et palette

| Élément | Code hex |
|---|---|
| T1 (foyer + formation) | `#d62728` |
| T2 (formation seule) | `#1f77b4` |
| T3 (contrôle) | `#7f7f7f` |
| Positif sig. | `#2ca02c` |
| Négatif sig. | `#d62728` |
| Non sig. | `#aec7e8` |

---

## Étape 5 — Page 1 : Vue d'ensemble

### Titre
Zone de texte : `RCT Foyers Améliorés — Résultats d'impact`
Sous-titre : `Design 3 bras · 1 850 ménages · ANCOVA + cluster SE`

### Cartes design (3 côte à côte)

| Carte | Valeur | Couleur titre |
|---|---|---|
| T1 — Foyer + Formation | 614 | `#d62728` |
| T2 — Formation seule | 616 | `#1f77b4` |
| T3 — Contrôle | 620 | `#7f7f7f` |

Créer via **Insertion → Carte** × 3. Taille : 140 × 70 px.

### KPI outcomes (2 cartes)
- Valeur : `Nb_Sig_T1` → Étiquette : `Outcomes sig. T1 vs T3`
- Valeur : `Nb_Sig_Foyer` → Étiquette : `Outcomes sig. (foyer seul)`

### Barres T1 vs T3 avec erreur

**Graphique à barres groupées** :
- Axe Y : `label_outcome`
- Axe X : `coef`
- Légende : `direction`
- Couleurs : Positif sig. = `#2ca02c` · Négatif sig. = `#d62728` · Non sig. = `#aec7e8`
- Filtre : `comparaison = "T1 vs T3 (total)"`
- Format → **Barres d'erreur** → Activer → Limite sup = `hi95` · Limite inf = `lo95`
- Ligne de référence à 0 : noire, continue

### Slicer
- Champ : `label_question` — style Liste

---

## Étape 6 — Page 2 : Résultats par question

### Slicers
- Slicer 1 : `label_question` (tuiles horizontales)
- Slicer 2 : `label_comparaison` (tuiles : 3 estimands)

### Forest plot (image)
**Insertion → Image** → `powerbi/screenshots/forest_plot_ancova_R.png`
Taille : 500 × 400 px · Titre : `Effets standardisés — IC 95%`

### Barres avec erreur (interactif)
**Graphique à barres groupées** :
- Axe Y : `label_outcome`
- Axe X : `coef`
- Légende : `label_comparaison`
- Couleurs : rouge / bleu / vert selon estimand
- Format → **Barres d'erreur** → Limite sup = `hi95` · Limite inf = `lo95`
- Ligne de référence à 0 : noire

### Table des effets
Colonnes : `label_outcome`, `label_comparaison`, `coef` (`+0.000;-0.000`), `se` (`0.000`), `pval_formatted`, `direction`

Mise en forme conditionnelle sur `coef` : dégradé rouge → blanc → vert.

---

## Étape 7 — Page 3 : Décomposition foyer vs formation

*Page unique à ce design 3 bras — la valeur ajoutée du foyer seul.*

### Zone de texte explicative

> *β₁ (T1 vs T3) = effet total (foyer + formation)*
> *β₂ (T2 vs T3) = effet formation seule*
> *β₁ − β₂ = effet marginal du foyer, conditionnel à la formation*
> *Si β₁ − β₂ ≈ 0 → l'effet vient de la formation. Si β₁ − β₂ > 0 → le foyer ajoute.*

### Barres 3 estimands côte à côte
**Graphique à barres groupées** :
- Axe Y : `label_outcome`
- Valeurs : `coef`
- Légende : `label_comparaison`
- Couleurs : rouge (T1 vs T3) / bleu (T2 vs T3) / vert (T1 vs T2)
- Barres d'erreur : `hi95` / `lo95`
- Ligne de référence à 0

*Ce graphique répond visuellement à : « le foyer ajoute-t-il un effet ? »*

### Matrice des moyennes par bras
**Visualisations → Matrice**
Source : `moyennes_par_bras`
- Lignes : `label_outcome`
- Colonnes : `bras` (T1, T2, T3)
- Valeurs : `moyenne` → Format `0.00`

### Insight clé (Zone de texte)
Remplir après analyse :
> *Résultat central : la formation seule réduit les tâches ménagères (β₂=−0.48h, p=0.01). Le foyer ajoute une réduction marginale (β₁−β₂=−0.30, p=0.09). L'effet sur les attitudes genre est porté par le foyer (β₁−β₂=+0.14**).*

---

## Étape 8 — Page 4 : Méthodes

### Table complète
Colonnes : `label_question`, `label_outcome`, `label_comparaison`, `coef` (+0.000), `se`, `pval_formatted`, `direction`, `n`

### Note méthodologique (Zone de texte)
```
NOTES MÉTHODOLOGIQUES

Design : RCT 3 bras, randomisation au niveau groupement.
Attrition : 0,05 % — non différentielle.
Estimateur : ANCOVA
  Y_E = a + b1*T1 + b2*T2 + g*Y_B + d*strate + eps
  SE clustérisés village (~800 villages).
Strates : 5 zones agro-écologiques (CENTRE fusionné).
Sources : CRDES, Sénégal. Python 3.12 + R fixest.
```

---

## Étape 9 — Navigation

**Insertion → Boutons → Vierge** × 4 par page :
- Labels : `Vue d'ensemble` / `Résultats` / `Décomposition` / `Méthodes`
- Format : rectangle arrondi, fond `#264653`, texte blanc 11pt
- Action : Navigation dans la page → destination respective

---

## Étape 10 — Export et commit

```bash
echo 'powerbi/*.pbix' >> .gitignore

git add powerbi/data/ powerbi/screenshots/ powerbi/GUIDE_CONSTRUCTION.md
git add python/03_export_dashboard_csv.py
git commit -m "Phase 2.6: Power BI RCT dashboard — 4 pages, 3-arm decomposition"
git push
```

---

## Référence rapide

| Page | Visual principal | Type Power BI |
|---|---|---|
| Vue d'ensemble | Barres T1 vs T3 + erreur | Barres groupées |
| Résultats | Forest plot + barres 3 estimands | Image + Barres |
| Décomposition foyer | Barres 3 estimands côte à côte | Barres groupées |
| Méthodes | Table complète + note | Table |
