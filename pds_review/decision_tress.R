# ==============================================================================
# MACHINE LEARNING MODELS IN R FOR OPTIONS EXECUTION PREDICTION
# Faculty: Dr. Vijayalakshmi A, Associate Professor, VIT Chennai
# Course: Data Analytics Solution using R
# ==============================================================================

# 1. Load Libraries (Already installed in your R session)
library(dplyr)
library(readr)
library(caret)
library(rpart)
library(rpart.plot)
library(randomForest)

# 2. Smart Path Resolution (Finds file automatically)
file_candidates <- c(
  "data/options_trade_signals_sample.csv",
  "options_trade_signals_sample.csv",
  "OPTIONS/data/options_trade_signals_sample.csv",
  "C:/Harsh/StockProject/HARSH/OPTIONS!!!!!/data/options_trade_signals_sample.csv",
  "C:/Harsh/StockProject/HARSH/OPTIONS!!!!!/OPTIONS/data/options_trade_signals_sample.csv"
)

target_file <- NULL
for (fp in file_candidates) {
  if (file.exists(fp)) {
    target_file <- fp
    break
  }
}

if (!is.null(target_file)) {
  message(">> Successfully loading dataset from: ", target_file)
  df <- read_csv(target_file, show_col_types = FALSE)
} else {
  stop("File not found! Please check working directory.")
}

# 3. Feature Engineering & Target Definition
set.seed(42)
df_ml <- df %>%
  mutate(
    # Target: 1 = Profitable (Top 50%), 0 = Unprofitable (Bottom 50%)
    target = factor(ifelse(execution_score >= median(execution_score), "Profitable", "Unprofitable")),
    log_volume = log1p(volume)
  ) %>%
  select(confidence, spread, log_volume, z_vwoim, z_oi_flow, target)

# 4. Train-Test Split (80% Train, 20% Test)
train_idx <- createDataPartition(df_ml$target, p = 0.8, list = FALSE)
train_data <- df_ml[train_idx, ]
test_data  <- df_ml[-train_idx, ]

message(">> Data split: ", nrow(train_data), " training rows, ", nrow(test_data), " test rows.")

# ------------------------------------------------------------------------------
# MODEL 1: DECISION TREE (CART)
# ------------------------------------------------------------------------------
message(">> Training Decision Tree (CART)...")
fit_dt <- rpart(target ~ ., data = train_data, method = "class", control = rpart.control(cp = 0.015))

# Plot the Decision Tree Diagram 
rpart.plot(fit_dt, 
           main = "Decision Tree: Options Trade Execution Rules", 
           box.palette = "RdBu", 
           shadow.col = "gray", 
           extra = 104,
           nn = TRUE)

pred_dt <- predict(fit_dt, newdata = test_data, type = "class")
cat("\n--- DECISION TREE CONFUSION MATRIX ---\n")
print(confusionMatrix(pred_dt, test_data$target))

# ------------------------------------------------------------------------------
# MODEL 2: RANDOM FOREST (BAGGING ENSEMBLE OF 100 TREES)
# ------------------------------------------------------------------------------
message(">> Training Random Forest (100 Trees)...")
fit_rf <- randomForest(target ~ ., data = train_data, ntree = 100, importance = TRUE)

pred_rf <- predict(fit_rf, newdata = test_data)
cat("\n--- RANDOM FOREST CONFUSION MATRIX ---\n")
print(confusionMatrix(pred_rf, test_data$target))

# Plot Feature Importance
varImpPlot(fit_rf, main = "Random Forest: Feature Importance Ranking", col = "blue", pch = 16)

message(">> [SUCCESS] Both Decision Tree and Random Forest trained and plotted in RStudio!")
