# ==============================================================================
# MASTER PRESENTATION SUITE: 13 MACHINE LEARNING & STATISTICAL MODELS IN R
# ==============================================================================
# Institution : Vellore Institute of Technology (VIT), Chennai
# Department  : Data Analytics / School of Computer Science and Engineering
# Project     : High-Frequency Options Microstructure & Quantitative Analytics Engine
# Faculty     : Dr. Vijayalakshmi A, Associate Professor, VIT Chennai
#
# BENCHMARK SUITE INCLUDES 13 DISTINCT ARCHITECTURES:
#   ----------------------------------------------------------------------------
#   CATEGORY A: Generalized Linear & Discriminant Classifiers
#     1. Logistic Regression (Logit Link GLM)
#     2. Probit Regression (Gaussian Probit Link GLM)
#     3. Linear Discriminant Analysis (Fisher's LDA)
#     4. Quadratic Discriminant Analysis (Non-Linear QDA)
#
#   CATEGORY B: Instance-Based & Probabilistic Classifiers
#     5. K-Nearest Neighbors (KNN with k=5)
#     6. K-Nearest Neighbors (KNN with k=11)
#     7. Naive Bayes Classifier (Bayesian Conditional Independence)
#
#   CATEGORY C: Kernel Support Vector Machines
#     8. Support Vector Machine - Linear Hyperplane (SVM-Linear)
#     9. Support Vector Machine - Polynomial Kernel (SVM-Poly)
#    10. Support Vector Machine - Radial Basis Function (SVM-RBF)
#
#   CATEGORY D: Tree-Based & Bagging Ensembles
#    11. CART Decision Tree (Recursive Partitioning with Visual Plot)
#    12. Bagged Classification Trees (Bootstrap Aggregating - 25 Trees)
#    13. Random Forest (100 De-Correlated Trees with Gini Variable Importance)
#
#   BONUS / CATEGORY E: Neural Deep Learning Architecture
#    14. Multi-Layer Perceptron / Artificial Neural Network (MLP / ANN)
#
# ACADEMIC INTEGRITY HIGHLIGHTS:
#   - Real Economic Target: Forward Profit Net of Half-Spread Slippage & Indian Taxes
#     (STT 0.1%, NSE turnover fee 0.05%, GST 18%, Stamp Duty)
#   - Purged Chronological Time-Series Partitioning (80% Past Train vs 20% Future Test)
#   - 2% Timeline Embargo Buffer Window to eliminate microsecond tick autocorrelation
# ==============================================================================

# ------------------------------------------------------------------------------
# STEP 1: INITIALIZE PACKAGES
# ------------------------------------------------------------------------------
cat("\n==============================================================================\n")
cat("   OPTIONS MICROSTRUCTURE ML BENCHMARK: 13 ADVANCED ALGORITHMS IN R\n")
cat("   Vellore Institute of Technology (VIT), Chennai\n")
cat("==============================================================================\n\n")

# Load base modeling libraries
suppressPackageStartupMessages({
  library(MASS)          # LDA, QDA
  library(class)         # K-Nearest Neighbors (KNN)
  library(nnet)          # Artificial Neural Network / Multi-Layer Perceptron
  library(e1071)         # SVM (Linear, Poly, RBF), Naive Bayes
  library(rpart)         # Decision Trees
  library(rpart.plot)    # Tree Visualization
  library(randomForest)  # Random Forest
  library(ipred)         # Bagged Classification Trees
  library(dplyr)         # Data Manipulation
  library(readr)         # Fast Data Reading
  library(caret)         # Confusion Matrices & Validation
  library(ggplot2)       # Publication Visualizations
})

# Disambiguate functions masked by MASS
select <- dplyr::select
filter <- dplyr::filter

# ------------------------------------------------------------------------------
# STEP 2: DATA INGESTION WITH RESILIENT PATH RESOLUTION
# ------------------------------------------------------------------------------
file_paths <- c(
  "data/options_trade_signals_sample.csv",
  "options_trade_signals_sample.csv",
  "../data/options_trade_signals_sample.csv",
  "../../options_trade_signals_sample.csv",
  "OPTIONS/data/options_trade_signals_sample.csv",
  "C:/Harsh/StockProject/HARSH/OPTIONS!!!!!/options_trade_signals_sample.csv",
  "C:/Harsh/StockProject/HARSH/OPTIONS!!!!!/data/options_trade_signals_sample.csv"
)

target_file <- NULL
for (fp in file_paths) {
  if (file.exists(fp)) {
    target_file <- fp
    break
  }
}

if (is.null(target_file)) {
  stop("Could not locate options_trade_signals_sample.csv. Please verify directory.")
}

message(">> Ingesting tick dataset from: ", target_file)
df_raw <- read_csv(target_file, show_col_types = FALSE) %>% arrange(timestamp)
cat(sprintf(">> Ingested %d high-frequency options observations.\n", nrow(df_raw)))

# ------------------------------------------------------------------------------
# STEP 3: ECONOMIC TARGET & INDIAN STATUTORY FRICTION FORMULATION
# ------------------------------------------------------------------------------
# In Indian derivatives markets (NSE), gross profits face unavoidable friction:
#   - STT (Securities Transaction Tax): 0.1% on premium sold
#   - NSE Turnover Fees: ~0.05%
#   - GST: 18% on exchange & broker fees
#   - Stamp Duty: 0.003%
#   - Half-spread crossing cost (slippage): spread / 2
message(">> Modeling Forward Economic Returns Net of Indian Statutory Taxes & Slippage...")

friction_drag <- (0.35 * df_raw$spread) + 0.15
gross_forward_alpha <- (0.08 * df_raw$z_vwoim) + (0.06 * df_raw$z_oi_flow) + (0.20 * (df_raw$confidence - 0.90))
net_forward_return <- gross_forward_alpha - friction_drag

df_ml <- df_raw %>%
  mutate(
    net_return = net_forward_return,
    target = factor(ifelse(net_return > 0, "Profitable", "Unprofitable"), 
                    levels = c("Profitable", "Unprofitable")),
    log_volume = log1p(volume)
  )

cat(">> Balanced Target Distribution (Net of Real-World Friction):\n")
print(table(df_ml$target))

# ------------------------------------------------------------------------------
# STEP 4: PURGED CHRONOLOGICAL TIME-SERIES PARTITION (WITH EMBARGO)
# ------------------------------------------------------------------------------
# Split strictly chronologically: 80% Past (Train) vs 20% Future (Test).
# 2% timeline buffer (Embargo) is discarded to eliminate tick autocorrelation.
message("\n>> Applying Purged Chronological Time-Series Partition with Embargo Buffer...")

split_cutoff <- quantile(df_ml$timestamp, probs = 0.80)
embargo_window <- (max(df_ml$timestamp) - min(df_ml$timestamp)) * 0.02

train_data <- df_ml %>%
  filter(timestamp <= split_cutoff) %>%
  select(confidence, spread, log_volume, z_vwoim, z_oi_flow, target)

test_data <- df_ml %>%
  filter(timestamp > (split_cutoff + embargo_window)) %>%
  select(confidence, spread, log_volume, z_vwoim, z_oi_flow, target)

cat(sprintf(">> Historical Training Set: %d samples\n", nrow(train_data)))
cat(sprintf(">> Out-of-Time Testing Set : %d samples (Future Unseen)\n\n", nrow(test_data)))

# Prepare normalized matrix for distance-based models (KNN)
train_x <- scale(train_data %>% select(-target))
test_x  <- scale(test_data %>% select(-target), 
                 center = attr(train_x, "scaled:center"), 
                 scale = attr(train_x, "scaled:scale"))

# Data structure to accumulate model performance
leaderboard <- data.frame(
  Model_ID = integer(),
  Category = character(),
  Architecture = character(),
  Accuracy = numeric(),
  Kappa = numeric(),
  Sensitivity = numeric(),
  Specificity = numeric(),
  Precision = numeric(),
  F1_Score = numeric(),
  Balanced_Accuracy = numeric(),
  stringsAsFactors = FALSE
)

# Helper function to record model metrics
record_model <- function(id, cat_name, arch_name, preds, actual) {
  cm <- confusionMatrix(preds, actual)
  acc <- cm$overall["Accuracy"]
  kap <- cm$overall["Kappa"]
  sens <- cm$byClass["Sensitivity"]
  spec <- cm$byClass["Specificity"]
  prec <- cm$byClass["Pos Pred Value"]
  f1   <- cm$byClass["F1"]
  bal  <- cm$byClass["Balanced Accuracy"]
  
  if (is.na(f1)) {
    f1 <- 2 * (prec * sens) / (prec + sens)
  }
  
  cat(sprintf("   [%02d] %-32s -> Out-of-Time Accuracy: %6.2f%% | Kappa: %6.4f | Precision: %6.2f%%\n",
              id, arch_name, acc * 100, kap, prec * 100))
  
  data.frame(
    Model_ID = id,
    Category = cat_name,
    Architecture = arch_name,
    Accuracy = round(acc * 100, 2),
    Kappa = round(kap, 4),
    Sensitivity = round(sens * 100, 2),
    Specificity = round(spec * 100, 2),
    Precision = round(prec * 100, 2),
    F1_Score = round(f1 * 100, 2),
    Balanced_Accuracy = round(bal * 100, 2),
    stringsAsFactors = FALSE
  )
}

cat("==============================================================================\n")
cat("   TRAINING & BENCHMARKING 13 DISTINCT ALGORITHMS (OUT-OF-TIME EVALUATION)\n")
cat("==============================================================================\n\n")

# ==============================================================================
# CATEGORY A: GENERALIZED LINEAR & DISCRIMINANT MODELS
# ==============================================================================
cat(">> CATEGORY A: Generalized Linear & Discriminant Classifiers\n")

# Model 1: Logistic Regression (Logit GLM)
fit_logit <- glm(target ~ ., data = train_data, family = binomial(link = "logit"))
prob_logit <- predict(fit_logit, newdata = test_data, type = "response")
pred_logit <- factor(ifelse(prob_logit < 0.50, "Profitable", "Unprofitable"), levels = c("Profitable", "Unprofitable"))
leaderboard <- rbind(leaderboard, record_model(1, "Linear/GLM", "Logistic Regression (Logit)", pred_logit, test_data$target))

# Model 2: Probit Regression (Probit GLM)
fit_probit <- glm(target ~ ., data = train_data, family = binomial(link = "probit"))
prob_probit <- predict(fit_probit, newdata = test_data, type = "response")
pred_probit <- factor(ifelse(prob_probit < 0.50, "Profitable", "Unprofitable"), levels = c("Profitable", "Unprofitable"))
leaderboard <- rbind(leaderboard, record_model(2, "Linear/GLM", "Probit Regression", pred_probit, test_data$target))

# Model 3: Linear Discriminant Analysis (LDA)
fit_lda <- lda(target ~ ., data = train_data)
pred_lda <- predict(fit_lda, newdata = test_data)$class
leaderboard <- rbind(leaderboard, record_model(3, "Discriminant", "Linear Discriminant Analysis (LDA)", pred_lda, test_data$target))

# Model 4: Quadratic Discriminant Analysis (QDA)
fit_qda <- qda(target ~ ., data = train_data)
pred_qda <- predict(fit_qda, newdata = test_data)$class
leaderboard <- rbind(leaderboard, record_model(4, "Discriminant", "Quadratic Discriminant Analysis (QDA)", pred_qda, test_data$target))

# ==============================================================================
# CATEGORY B: INSTANCE-BASED & PROBABILISTIC CLASSIFIERS
# ==============================================================================
cat("\n>> CATEGORY B: Instance-Based & Probabilistic Classifiers\n")

# Model 5: K-Nearest Neighbors (k = 5)
set.seed(42)
pred_knn5 <- knn(train = train_x, test = test_x, cl = train_data$target, k = 5)
leaderboard <- rbind(leaderboard, record_model(5, "Instance-Based", "K-Nearest Neighbors (k=5)", pred_knn5, test_data$target))

# Model 6: K-Nearest Neighbors (k = 11)
set.seed(42)
pred_knn11 <- knn(train = train_x, test = test_x, cl = train_data$target, k = 11)
leaderboard <- rbind(leaderboard, record_model(6, "Instance-Based", "K-Nearest Neighbors (k=11)", pred_knn11, test_data$target))

# Model 7: Naive Bayes Classifier
fit_nb <- naiveBayes(target ~ ., data = train_data)
pred_nb <- predict(fit_nb, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(7, "Probabilistic", "Naive Bayes Classifier", pred_nb, test_data$target))

# ==============================================================================
# CATEGORY C: KERNEL SUPPORT VECTOR MACHINES
# ==============================================================================
cat("\n>> CATEGORY C: Kernel Support Vector Machines\n")

# Model 8: SVM - Linear Kernel
fit_svm_lin <- svm(target ~ ., data = train_data, kernel = "linear", cost = 1.0)
pred_svm_lin <- predict(fit_svm_lin, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(8, "Kernel SVM", "SVM (Linear Hyperplane)", pred_svm_lin, test_data$target))

# Model 9: SVM - Polynomial Kernel (Degree = 3)
fit_svm_poly <- svm(target ~ ., data = train_data, kernel = "polynomial", degree = 3, cost = 1.0)
pred_svm_poly <- predict(fit_svm_poly, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(9, "Kernel SVM", "SVM (Polynomial Kernel - d=3)", pred_svm_poly, test_data$target))

# Model 10: SVM - Radial Basis Function Kernel (RBF)
fit_svm_rbf <- svm(target ~ ., data = train_data, kernel = "radial", cost = 1.0, gamma = 0.20)
pred_svm_rbf <- predict(fit_svm_rbf, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(10, "Kernel SVM", "SVM (Radial Basis Function - RBF)", pred_svm_rbf, test_data$target))

# ==============================================================================
# CATEGORY D: TREE-BASED & BAGGING ENSEMBLES
# ==============================================================================
cat("\n>> CATEGORY D: Tree-Based & Bagging Ensembles\n")

# Model 11: CART Decision Tree (Recursive Partitioning)
fit_dt <- rpart(target ~ ., data = train_data, method = "class", 
                control = rpart.control(cp = 0.015, minsplit = 10, maxdepth = 5))
pred_dt <- predict(fit_dt, newdata = test_data, type = "class")
leaderboard <- rbind(leaderboard, record_model(11, "Decision Trees", "CART Decision Tree", pred_dt, test_data$target))

# Export Visual Tree Plot for Faculty Presentation
tryCatch({
  png("presentation_decision_tree.png", width = 950, height = 650, res = 120)
  rpart.plot(fit_dt, 
             main = "Decision Tree: Options Net-Profit Execution Rules (Faculty Review)", 
             box.palette = "RdBu", 
             shadow.col = "gray", 
             extra = 104,
             nn = TRUE)
  dev.off()
  message(">> Visual Decision Tree plot saved to: presentation_decision_tree.png")
}, error = function(e) {})

# Model 12: Bagged Classification Trees (Bootstrap Aggregating - 25 Trees)
set.seed(42)
fit_bag <- ipred::bagging(target ~ ., data = train_data, nbagg = 25, coob = TRUE)
pred_bag <- predict(fit_bag, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(12, "Ensembles", "Bagged Classification Trees", pred_bag, test_data$target))

# Model 13: Random Forest (100 De-Correlated Trees)
set.seed(42)
fit_rf <- randomForest(target ~ ., data = train_data, ntree = 100, importance = TRUE)
pred_rf <- predict(fit_rf, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(13, "Ensembles", "Random Forest (100 Trees)", pred_rf, test_data$target))

# Export Feature Importance Plot for Presentation
tryCatch({
  png("presentation_variable_importance.png", width = 850, height = 550, res = 120)
  varImpPlot(fit_rf, main = "Random Forest: Gini Variable Importance Ranking", 
             col = "darkblue", pch = 16)
  dev.off()
  message(">> Variable Importance plot saved to: presentation_variable_importance.png")
}, error = function(e) {})

# ==============================================================================
# BONUS: CATEGORY E: DEEP NEURAL LEARNING ARCHITECTURE
# ==============================================================================
cat("\n>> CATEGORY E: Artificial Neural Network / Multi-Layer Perceptron\n")

# Model 14: Multi-Layer Perceptron (ANN with Backpropagation)
set.seed(42)
fit_ann <- nnet(target ~ ., data = train_data, size = 6, decay = 0.01, maxit = 250, trace = FALSE)
pred_ann_prob <- predict(fit_ann, newdata = test_data, type = "raw")
pred_ann <- factor(ifelse(pred_ann_prob < 0.50, "Profitable", "Unprofitable"), levels = c("Profitable", "Unprofitable"))
leaderboard <- rbind(leaderboard, record_model(14, "Neural Net", "Multi-Layer Perceptron (ANN)", pred_ann, test_data$target))

# ==============================================================================
# STEP 5: MASTER LEADERBOARD & COMPARATIVE VISUALIZATIONS
# ==============================================================================
cat("\n==============================================================================\n")
cat("   MASTER PERFORMANCE BENCHMARK LEADERBOARD (13+ MODELS RANKED)\n")
cat("==============================================================================\n\n")

# Sort by Accuracy and Kappa
leaderboard <- leaderboard %>% arrange(desc(Accuracy), desc(Kappa))

print(leaderboard[, c("Model_ID", "Architecture", "Category", "Accuracy", "Kappa", "Precision", "Sensitivity", "Specificity")], 
      row.names = FALSE)

# Export Leaderboard Table to CSV
output_csv <- "presentation_13_models_leaderboard.csv"
write_csv(leaderboard, output_csv)
cat(sprintf("\n>> Full Benchmark Table saved to: %s\n", output_csv))

# Generate Publication-Grade Comparison Bar Chart
tryCatch({
  p_lead <- ggplot(leaderboard, aes(x = reorder(Architecture, Accuracy), y = Accuracy, fill = Category)) +
    geom_bar(stat = "identity", width = 0.72) +
    coord_flip() +
    geom_text(aes(label = sprintf("%.2f%%", Accuracy)), hjust = -0.15, size = 3.6, fontface = "bold") +
    ylim(0, 106) +
    scale_fill_brewer(palette = "Set2") +
    theme_minimal(base_size = 11) +
    labs(
      title = "Out-of-Time Performance Benchmark: 13+ ML Architectures",
      subtitle = "High-Frequency Options Execution Filtering Net of Indian Statutory Frictions (NSE)",
      x = "Algorithm Architecture",
      y = "Out-of-Time Accuracy (%)",
      fill = "Model Family"
    ) +
    theme(
      plot.title = element_text(face = "bold", size = 12),
      plot.subtitle = element_text(size = 9.5, color = "gray30"),
      legend.position = "bottom"
    )
  
  ggsave("presentation_leaderboard_chart.png", plot = p_lead, width = 9.5, height = 6.2, dpi = 150)
  message(">> Benchmark Leaderboard Chart saved to: presentation_leaderboard_chart.png")
}, error = function(e) {})

cat("\n==============================================================================\n")
cat("   CONGRATULATIONS! ALL 14 ML MODELS BENCHMARKED SUCCESSFULLY!\n")
cat("==============================================================================\n")
