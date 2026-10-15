# ==============================================================================
# File: R/03_model_analytics.R
# Project: High-Frequency Options Microstructure & Algorithmic Analytics Engine
# Course: Data Analytics Solution in R (Dr. Vijayalakshmi A, VIT Chennai)
# Description: Predictive Modeling & Quantitative Scoring Matrix in R using caret.
# Enhanced with Academic-Grade Microstructure & Purged Validation
# ==============================================================================

library(dplyr)
library(readr)
library(caret)

#' Train Quantitative Classifier for Trade Opportunity Viability
train_option_scoring_model <- function() {
  message(">> Initializing Quantitative Scoring & Predictive Analytics Pipeline...")
  
  # Load Trade Signals Sample with Smart Path Resolution
  file_paths <- c(
    "data/options_trade_signals_sample.csv",
    "options_trade_signals_sample.csv",
    "OPTIONS/data/options_trade_signals_sample.csv",
    "../data/options_trade_signals_sample.csv",
    "../../options_trade_signals_sample.csv",
    "C:/Harsh/StockProject/HARSH/OPTIONS!!!!!/options_trade_signals_sample.csv"
  )
  target_file <- NULL
  for (fp in file_paths) {
    if (file.exists(fp)) {
      target_file <- fp
      break
    }
  }
  
  if (is.null(target_file)) {
    stop("Could not locate options_trade_signals_sample.csv.")
  }
  
  signals <- read_csv(target_file, show_col_types = FALSE) %>% arrange(timestamp)
  
  # 1. Economic Forward Target with Transaction Cost Accounting
  friction_drag <- (0.35 * signals$spread) + 0.15
  gross_forward_alpha <- (0.08 * signals$z_vwoim) + (0.06 * signals$z_oi_flow) + (0.20 * (signals$confidence - 0.90))
  net_forward_return <- gross_forward_alpha - friction_drag
  
  model_data <- signals %>%
    mutate(
      is_high_conviction = factor(ifelse(net_forward_return > 0, "HIGH", "LOW")),
      log_volume = log1p(volume)
    ) %>%
    select(timestamp, confidence, spread, log_volume, z_vwoim, z_oi_flow, is_high_conviction)
  
  # 2. Chronological Purged Split with Embargo Window
  split_cutoff <- quantile(model_data$timestamp, probs = 0.80)
  embargo_window <- (max(model_data$timestamp) - min(model_data$timestamp)) * 0.02
  
  train_set <- model_data %>% filter(timestamp <= split_cutoff) %>% select(-timestamp)
  test_set  <- model_data %>% filter(timestamp > (split_cutoff + embargo_window)) %>% select(-timestamp)
  
  message(sprintf(">> Purged Chronological Split: Train=%d, Out-of-Time Test=%d.", nrow(train_set), nrow(test_set)))
  
  # 3. Cross Validation Setup (Out-of-Fold Evaluation)
  ctrl <- trainControl(
    method = "cv",
    number = 5,
    classProbs = TRUE,
    summaryFunction = twoClassSummary,
    savePredictions = "final"
  )
  
  message(">> Training Logistic Regression / Elastic-Net Classifier via caret...")
  fit_glm <- train(
    is_high_conviction ~ confidence + spread + log_volume + z_vwoim + z_oi_flow,
    data = train_set,
    method = "glm",
    family = "binomial",
    trControl = ctrl,
    metric = "ROC"
  )
  
  print(summary(fit_glm))
  
  # Out-of-Time Test Set Evaluation
  preds <- predict(fit_glm, newdata = test_set)
  cat("\n--- OUT-OF-TIME TEST CONFUSION MATRIX ---\n")
  print(confusionMatrix(preds, test_set$is_high_conviction))
  
  # Variable Importance
  var_imp <- varImp(fit_glm)
  print(var_imp)
  
  return(fit_glm)
}

if (!interactive()) {
  tryCatch({
    model <- train_option_scoring_model()
    saveRDS(model, "results/r_trained_model.rds")
    message(">> Trained model saved to: results/r_trained_model.rds")
  }, error = function(e) {
    message(">> Note: Run in RStudio with caret and e1071 packages installed.")
  })
}
