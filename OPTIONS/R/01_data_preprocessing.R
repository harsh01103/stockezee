# ==============================================================================
# File: R/01_data_preprocessing.R
# Project: High-Frequency Options Microstructure & Algorithmic Analytics Engine
# Course: Data Analytics Solution in R (Dr. Vijayalakshmi A, VIT Chennai)
# Description: Modular R pipeline for data acquisition, cleaning, deduplication,
#              feature engineering, and Time-of-Day (TOD) robust normalization.
# ==============================================================================

library(dplyr)
library(readr)
library(tidyr)
library(lubridate)

#' Load and Clean Options Raw Tick Data
#' @param file_path Path to the raw CSV or Parquet export
#' @return A preprocessed tibble ready for exploratory data analysis
load_and_preprocess_options <- function(file_path = "data/raw_sample_dataset.csv") {
  message(">> Loading raw options tick dataset from: ", file_path)
  
  if (!file.exists(file_path)) {
    stop("Raw data file not found at: ", file_path)
  }
  
  # 1. Ingest Raw Dataset
  raw_data <- read_csv(
    file_path,
    col_types = cols(
      timestamp = col_double(),
      exchange_timestamp = col_double(),
      underlying = col_character(),
      expiry = col_character(),
      strike = col_double(),
      option_type = col_character(),
      spot = col_double(),
      ltp = col_double(),
      bid = col_double(),
      ask = col_double(),
      volume = col_double(),
      oi = col_double(),
      latency_ms = col_double()
    )
  )
  
  message(sprintf("   Loaded %d raw ticks across %s.", nrow(raw_data), paste(unique(raw_data$underlying), collapse = ", ")))
  
  # 2. Primary Key Deduplication
  # Retain the most recent tick for identical composite keys
  cleaned_data <- raw_data %>%
    distinct(timestamp, underlying, expiry, strike, option_type, .keep_all = TRUE)
  
  dupes_removed <- nrow(raw_data) - nrow(cleaned_data)
  message(sprintf("   Removed %d duplicate ticks (Composite Key: timestamp, underlying, expiry, strike, option_type).", dupes_removed))
  
  # 3. Microstructure Feature Engineering
  processed_data <- cleaned_data %>%
    filter(strike > 0) %>% # Filter out index spot ticks for option analytics
    mutate(
      datetime = as_datetime(timestamp / 1000, tz = "Asia/Kolkata"),
      session_slot = format(datetime, "%H:%M"),
      spread = ask - bid,
      spread_pct = ifelse(ltp > 0, (ask - bid) / ltp, 0),
      mid_price = (ask + bid) / 2,
      moneyness = ifelse(strike > 0, spot / strike, 1.0),
      atm_distance = strike - spot
    ) %>%
    arrange(underlying, expiry, strike, option_type, timestamp)
  
  # 4. Sequential Flow Deltas (Delta OI and Delta Volume)
  processed_data <- processed_data %>%
    group_by(underlying, expiry, strike, option_type) %>%
    mutate(
      delta_oi = oi - lag(oi, default = first(oi)),
      delta_volume = volume - lag(volume, default = first(volume))
    ) %>%
    ungroup()
  
  # 5. Time-of-Day (TOD) Robust Z-Score Normalization
  # Utilizes Median and Interquartile Range (IQR) to mitigate morning/closing volume skew
  tod_stats <- processed_data %>%
    group_by(session_slot, underlying) %>%
    summarize(
      vol_median = median(volume, na.rm = TRUE),
      vol_iqr = IQR(volume, na.rm = TRUE) + 1e-6,
      oi_median = median(oi, na.rm = TRUE),
      oi_iqr = IQR(oi, na.rm = TRUE) + 1e-6,
      .groups = "drop"
    )
  
  final_data <- processed_data %>%
    left_join(tod_stats, by = c("session_slot", "underlying")) %>%
    mutate(
      volume_zscore_15m = pmax(-10, pmin(10, (volume - vol_median) / vol_iqr)),
      oi_zscore_15m = pmax(-10, pmin(10, (oi - oi_median) / oi_iqr))
    ) %>%
    select(-vol_median, -vol_iqr, -oi_median, -oi_iqr)
  
  message(sprintf(">> Data Preprocessing Completed successfully. Output rows: %d.", nrow(final_data)))
  return(final_data)
}

# If run as standalone script
if (!interactive()) {
  df <- load_and_preprocess_options()
  write_csv(df, "data/r_preprocessed_output.csv")
  message(">> Cleaned preprocessed dataset written to: data/r_preprocessed_output.csv")
}
