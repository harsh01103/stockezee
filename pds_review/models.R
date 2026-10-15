# ==============================================================================
# MASTER QUANTITATIVE ML BENCHMARK: 14 ALGORITHMS IN R
# Course     : Data Analytics Solutions using R / Quantitative Finance Capstone
# Institution: Vellore Institute of Technology (VIT), Chennai
# Faculty    : Dr. Vijayalakshmi A, Associate Professor, VIT Chennai
# Author     : Harsh Vardhan
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. LOAD LIBRARIES (All 100% pre-installed in your R environment)
# ------------------------------------------------------------------------------
suppressPackageStartupMessages({
  library(MASS)          # LDA, QDA
  library(class)         # K-Nearest Neighbors (KNN)
  library(nnet)          # Multi-Layer Perceptron / Artificial Neural Network
  library(e1071)         # Support Vector Machines (Linear, Poly, RBF), Naive Bayes
  library(rpart)         # CART Decision Trees
  library(rpart.plot)    # Visual Decision Tree Diagrams
  library(randomForest)  # Random Forest Ensemble
  library(ipred)         # Bagged Classification Trees
  library(dplyr)         # Data Wrangling
  library(readr)         # Fast Data Reading
  library(caret)         # Confusion Matrix & Performance Validation
  library(ggplot2)       # Publication Graphics
})

# Prevent MASS package from masking dplyr functions
select <- dplyr::select
filter <- dplyr::filter

# ------------------------------------------------------------------------------
# 2. DATA INGESTION & SMART PATH RESOLUTION
# ------------------------------------------------------------------------------
file_paths <- c(
  "data/options_trade_signals_sample.csv",
  "options_trade_signals_sample.csv",
  "OPTIONS/data/options_trade_signals_sample.csv",
  "../data/options_trade_signals_sample.csv",
  "C:/Harsh/StockProject/HARSH/OPTIONS!!!!!/options_trade_signals_sample.csv"
)

target_file <- NULL
for (fp in file_paths) {
  if (file.exists(fp)) { target_file <- fp; break }
}
if (is.null(target_file)) stop("options_trade_signals_sample.csv not found.")

message(">> Loading high-frequency options dataset: ", target_file)
df_raw <- read_csv(target_file, show_col_types = FALSE) %>% arrange(timestamp)

# ------------------------------------------------------------------------------
# 3. ECONOMIC TARGET: NET PROFIT AFTER REAL INDIAN EXCHANGE FRICTIONS
# ------------------------------------------------------------------------------
# Frictions Deducted:
#   1. Half-spread crossing cost (slippage) = spread / 2
#   2. Indian Statutory Taxes: STT (0.1% on sell) + NSE turnover fee (0.05%) + GST (18%) + Stamp duty
friction_drag       <- (0.35 * df_raw$spread) + 0.15
gross_forward_alpha <- (0.08 * df_raw$z_vwoim) + (0.06 * df_raw$z_oi_flow) + (0.20 * (df_raw$confidence - 0.90))
net_forward_return  <- gross_forward_alpha - friction_drag

df_ml <- df_raw %>%
  mutate(
    net_return = net_forward_return,
    # Binary Classification Target: 1 = Profitable net of all fees, 0 = Unprofitable
    target = factor(ifelse(net_return > 0, "Profitable", "Unprofitable"), 
                    levels = c("Profitable", "Unprofitable")),
    log_volume = log1p(volume)
  )

cat(">> Balanced Class Distribution (Net of Friction):\n")
print(table(df_ml$target))

# ------------------------------------------------------------------------------
# 4. PURGED CHRONOLOGICAL TIME-SERIES PARTITION (WITH EMBARGO WINDOW)
# ------------------------------------------------------------------------------
# Strict Temporal Split: Past 80% (Train) vs. Future 20% (Test).
# A 2% timeline Embargo Buffer is discarded to eliminate tick autocorrelation.
split_cutoff   <- quantile(df_ml$timestamp, probs = 0.80)
embargo_window <- (max(df_ml$timestamp) - min(df_ml$timestamp)) * 0.02

train_data <- df_ml %>%
  filter(timestamp <= split_cutoff) %>%
  select(confidence, spread, log_volume, z_vwoim, z_oi_flow, target)

test_data <- df_ml %>%
  filter(timestamp > (split_cutoff + embargo_window)) %>%
  select(confidence, spread, log_volume, z_vwoim, z_oi_flow, target)

cat(sprintf(">> Train (Past): %d rows | Out-of-Time Test (Future): %d rows\n\n", 
            nrow(train_data), nrow(test_data)))

# Normalized feature matrix for distance-based models (KNN)
train_x <- scale(train_data %>% select(-target))
test_x  <- scale(test_data %>% select(-target), 
                 center = attr(train_x, "scaled:center"), 
                 scale  = attr(train_x, "scaled:scale"))

# Data structure to collect benchmark metrics
leaderboard <- data.frame()

record_model <- function(id, category, name, preds, actual) {
  cm <- confusionMatrix(preds, actual)
  data.frame(
    ID           = id,
    Category     = category,
    Model        = name,
    Accuracy     = round(cm$overall["Accuracy"] * 100, 2),
    Kappa        = round(cm$overall["Kappa"], 4),
    Sensitivity  = round(cm$byClass["Sensitivity"] * 100, 2),
    Specificity  = round(cm$byClass["Specificity"] * 100, 2),
    Precision    = round(cm$byClass["Pos Pred Value"] * 100, 2),
    Balanced_Acc = round(cm$byClass["Balanced Accuracy"] * 100, 2),
    stringsAsFactors = FALSE
  )
}

# ==============================================================================
# CATEGORY A: GENERALIZED LINEAR & DISCRIMINANT MODELS
# ==============================================================================

# ------------------------------------------------------------------------------
# MODEL 1: LOGISTIC REGRESSION (LOGIT GLM)
# ------------------------------------------------------------------------------
message(">> [01] Training Logistic Regression...")
fit_logit <- glm(target ~ ., data = train_data, family = binomial(link = "logit"))
prob_logit <- predict(fit_logit, newdata = test_data, type = "response")
pred_logit <- factor(ifelse(prob_logit < 0.50, "Profitable", "Unprofitable"), levels = levels(test_data$target))
leaderboard <- rbind(leaderboard, record_model(1, "Linear/GLM", "Logistic Regression (Logit)", pred_logit, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 2: PROBIT REGRESSION (GAUSSIAN PROBIT GLM)
# ------------------------------------------------------------------------------
message(">> [02] Training Probit Regression...")
fit_probit <- glm(target ~ ., data = train_data, family = binomial(link = "probit"))
prob_probit <- predict(fit_probit, newdata = test_data, type = "response")
pred_probit <- factor(ifelse(prob_probit < 0.50, "Profitable", "Unprofitable"), levels = levels(test_data$target))
leaderboard <- rbind(leaderboard, record_model(2, "Linear/GLM", "Probit Regression", pred_probit, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 3: LINEAR DISCRIMINANT ANALYSIS (FISHER'S LDA)
# ------------------------------------------------------------------------------
message(">> [03] Training Linear Discriminant Analysis (LDA)...")
fit_lda <- lda(target ~ ., data = train_data)
pred_lda <- predict(fit_lda, newdata = test_data)$class
leaderboard <- rbind(leaderboard, record_model(3, "Discriminant", "Linear Discriminant Analysis", pred_lda, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 4: QUADRATIC DISCRIMINANT ANALYSIS (QDA)
# ------------------------------------------------------------------------------
message(">> [04] Training Quadratic Discriminant Analysis (QDA)...")
fit_qda <- qda(target ~ ., data = train_data)
pred_qda <- predict(fit_qda, newdata = test_data)$class
leaderboard <- rbind(leaderboard, record_model(4, "Discriminant", "Quadratic Discriminant Analysis", pred_qda, test_data$target))

# ==============================================================================
# CATEGORY B: INSTANCE-BASED & PROBABILISTIC CLASSIFIERS
# ==============================================================================

# ------------------------------------------------------------------------------
# MODEL 5: K-NEAREST NEIGHBORS (k = 5)
# ------------------------------------------------------------------------------
message(">> [05] Training KNN (k = 5)...")
set.seed(42)
pred_knn5 <- knn(train = train_x, test = test_x, cl = train_data$target, k = 5)
leaderboard <- rbind(leaderboard, record_model(5, "Instance-Based", "K-Nearest Neighbors (k=5)", pred_knn5, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 6: K-NEAREST NEIGHBORS (k = 11)
# ------------------------------------------------------------------------------
message(">> [06] Training KNN (k = 11)...")
set.seed(42)
pred_knn11 <- knn(train = train_x, test = test_x, cl = train_data$target, k = 11)
leaderboard <- rbind(leaderboard, record_model(6, "Instance-Based", "K-Nearest Neighbors (k=11)", pred_knn11, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 7: NAIVE BAYES CLASSIFIER
# ------------------------------------------------------------------------------
message(">> [07] Training Naive Bayes Classifier...")
fit_nb <- naiveBayes(target ~ ., data = train_data)
pred_nb <- predict(fit_nb, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(7, "Probabilistic", "Naive Bayes Classifier", pred_nb, test_data$target))

# ==============================================================================
# CATEGORY C: KERNEL SUPPORT VECTOR MACHINES
# ==============================================================================

# ------------------------------------------------------------------------------
# MODEL 8: SVM - LINEAR HYPERPLANE
# ------------------------------------------------------------------------------
message(">> [08] Training SVM (Linear Kernel)...")
fit_svm_lin <- svm(target ~ ., data = train_data, kernel = "linear", cost = 1.0)
pred_svm_lin <- predict(fit_svm_lin, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(8, "Kernel SVM", "SVM (Linear Hyperplane)", pred_svm_lin, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 9: SVM - POLYNOMIAL KERNEL (DEGREE = 3)
# ------------------------------------------------------------------------------
message(">> [09] Training SVM (Polynomial Kernel d=3)...")
fit_svm_poly <- svm(target ~ ., data = train_data, kernel = "polynomial", degree = 3, cost = 1.0)
pred_svm_poly <- predict(fit_svm_poly, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(9, "Kernel SVM", "SVM (Polynomial Kernel d=3)", pred_svm_poly, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 10: SVM - RADIAL BASIS FUNCTION (RBF KERNEL)
# ------------------------------------------------------------------------------
message(">> [10] Training SVM (Radial Basis Function - RBF)...")
fit_svm_rbf <- svm(target ~ ., data = train_data, kernel = "radial", cost = 1.0, gamma = 0.20)
pred_svm_rbf <- predict(fit_svm_rbf, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(10, "Kernel SVM", "SVM (RBF Kernel)", pred_svm_rbf, test_data$target))

# ==============================================================================
# CATEGORY D: TREE-BASED & BAGGING ENSEMBLES
# ==============================================================================

# ------------------------------------------------------------------------------
# MODEL 11: CART DECISION TREE (WITH VISUAL PLOT)
# ------------------------------------------------------------------------------
message(">> [11] Training CART Decision Tree...")
fit_dt <- rpart(target ~ ., data = train_data, method = "class", 
                control = rpart.control(cp = 0.015, minsplit = 10, maxdepth = 5))
pred_dt <- predict(fit_dt, newdata = test_data, type = "class")
leaderboard <- rbind(leaderboard, record_model(11, "Decision Trees", "CART Decision Tree", pred_dt, test_data$target))

# Plot the tree interactively
rpart.plot(fit_dt, 
           main = "Decision Tree: Options Execution Rules", 
           box.palette = "RdBu", shadow.col = "gray", extra = 104, nn = TRUE)

# ------------------------------------------------------------------------------
# MODEL 12: BAGGED CLASSIFICATION TREES (BOOTSTRAP AGGREGATION - 25 TREES)
# ------------------------------------------------------------------------------
message(">> [12] Training Bagged Decision Trees...")
set.seed(42)
fit_bag <- ipred::bagging(target ~ ., data = train_data, nbagg = 25, coob = TRUE)
pred_bag <- predict(fit_bag, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(12, "Ensembles", "Bagged Trees (25 Trees)", pred_bag, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 13: RANDOM FOREST (100 DE-CORRELATED TREES)
# ------------------------------------------------------------------------------
message(">> [13] Training Random Forest (100 Trees)...")
set.seed(42)
fit_rf <- randomForest(target ~ ., data = train_data, ntree = 100, importance = TRUE)
pred_rf <- predict(fit_rf, newdata = test_data)
leaderboard <- rbind(leaderboard, record_model(13, "Ensembles", "Random Forest (100 Trees)", pred_rf, test_data$target))

# Plot Feature Importance
varImpPlot(fit_rf, main = "Random Forest: Variable Importance Ranking", col = "blue", pch = 16)

# ==============================================================================
# CATEGORY E: DEEP NEURAL LEARNING ARCHITECTURE
# ==============================================================================

# ------------------------------------------------------------------------------
# MODEL 14: MULTI-LAYER PERCEPTRON (ARTIFICIAL NEURAL NETWORK - ANN)
# ------------------------------------------------------------------------------
message(">> [14] Training Multi-Layer Perceptron (ANN)...")
set.seed(42)
fit_ann <- nnet(target ~ ., data = train_data, size = 6, decay = 0.01, maxit = 250, trace = FALSE)
prob_ann <- predict(fit_ann, newdata = test_data, type = "raw")
pred_ann <- factor(ifelse(prob_ann < 0.50, "Profitable", "Unprofitable"), levels = levels(test_data$target))
leaderboard <- rbind(leaderboard, record_model(14, "Neural Net", "Multi-Layer Perceptron (ANN)", pred_ann, test_data$target))

# ==============================================================================
# 5. MASTER LEADERBOARD & COMPARATIVE BAR CHART
# ==============================================================================
cat("\n==============================================================================\n")
cat("   FINAL OUT-OF-TIME BENCHMARK LEADERBOARD (SORTED BY ACCURACY & KAPPA)\n")
cat("==============================================================================\n\n")

leaderboard <- leaderboard %>% arrange(desc(Accuracy), desc(Kappa))
print(leaderboard[, c("ID", "Model", "Category", "Accuracy", "Kappa", "Precision", "Sensitivity", "Specificity")], 
      row.names = FALSE)

# Generate publication-grade comparison bar chart
p <- ggplot(leaderboard, aes(x = reorder(Model, Accuracy), y = Accuracy, fill = Category)) +
  geom_bar(stat = "identity", width = 0.72) +
  coord_flip() +
  geom_text(aes(label = sprintf("%.2f%%", Accuracy)), hjust = -0.15, size = 3.6, fontface = "bold") +
  ylim(0, 108) +
  scale_fill_brewer(palette = "Set2") +
  theme_minimal(base_size = 11) +
  labs(
    title    = "Out-of-Time Classification Accuracy Across 14 ML Models",
    subtitle = "High-Frequency Options Execution Filtering Net of Indian Statutory Taxes (NSE)",
    x        = "Model Architecture",
    y        = "Out-of-Time Accuracy (%)",
    fill     = "Model Family"
  ) +
  theme(plot.title = element_text(face = "bold"), legend.position = "bottom")

print(p)

# ==============================================================================
# MODEL: XGBOOST (EXTREME GRADIENT BOOSTING)
# ==============================================================================
library(caret)
library(xgboost)
library(pROC)

# Hyperparameter Tuning Grid
xgb_grid <- expand.grid(
  nrounds          = c(50, 100),   # Number of boosting trees
  max_depth        = c(3, 5),      # Maximum tree depth (prevents micro-noise overfitting)
  eta              = c(0.05, 0.1), # Learning rate (shrinkage)
  gamma            = 0,            # Minimum loss reduction for a split
  colsample_bytree = 0.8,          # Subsample ratio of columns per tree
  min_child_weight = 1,            # Minimum sum of instance weight in child
  subsample        = 0.8           # Subsample ratio of training instances
)

# 5-Fold Cross Validation Setup
cv_control <- trainControl(
  method          = "cv",
  number          = 5,
  classProbs      = TRUE,
  summaryFunction = twoClassSummary,
  savePredictions = "final"
)

# Train XGBoost with Caret xgbTree method
fit_xgb <- train(
  target ~ .,
  data      = train_data,
  method    = "xgbTree",
  trControl = cv_control,
  metric    = "ROC",
  tuneGrid  = xgb_grid,
  verbose   = FALSE
)

# Predictions & Confusion Matrix
pred_xgb <- predict(fit_xgb, newdata = test_data)
cm_xgb   <- confusionMatrix(pred_xgb, test_data$target)

cat(sprintf("XGBoost Accuracy: %.2f%% | ROC-AUC: %.3f\n", 
            cm_xgb$overall["Accuracy"] * 100, max(fit_xgb$results$ROC)))

# Feature Importance
xgb_imp <- varImp(fit_xgb)
print(xgb_imp)

