# ==============================================================================
# File: R/02_exploratory_data_analysis.R
# Project: High-Frequency Options Microstructure & Algorithmic Analytics Engine
# Course: Data Analytics Solution in R (Dr. Vijayalakshmi A, VIT Chennai)
# Description: Generates EDA visualizations using ggplot2 and tidyverse.
# ==============================================================================

library(dplyr)
library(readr)
library(ggplot2)
library(scales)

# Set custom publication-quality dark aesthetic theme
theme_quant <- function() {
  theme_minimal(base_size = 12) +
    theme(
      plot.background = element_rect(fill = "#121418", color = NA),
      panel.background = element_rect(fill = "#1a1d24", color = NA),
      panel.grid.major = element_line(color = "#2a2f3a", linewidth = 0.5),
      panel.grid.minor = element_blank(),
      text = element_text(color = "#e5e7eb"),
      axis.text = element_text(color = "#9ca3af"),
      axis.title = element_text(color = "#f3f4f6", face = "bold"),
      plot.title = element_text(color = "#ffffff", face = "bold", size = 14, hjust = 0),
      plot.subtitle = element_text(color = "#9ca3af", size = 11),
      legend.background = element_rect(fill = "#1a1d24", color = "#2a2f3a"),
      legend.text = element_text(color = "#e5e7eb")
    )
}

# 1. Load Preprocessed Data
df <- read_csv("data/sample_preprocessed_features.csv", show_col_types = FALSE)

# 2. Plot 1: Open Interest Distribution (Max Pain Analysis)
nifty_oi <- df %>%
  filter(underlying == "NIFTY") %>%
  group_by(strike, option_type) %>%
  summarize(max_oi = max(oi, na.rm = TRUE), .groups = "drop")

p1 <- ggplot(nifty_oi, aes(x = factor(strike), y = max_oi, fill = option_type)) +
  geom_col(position = "dodge", alpha = 0.85, width = 0.7) +
  scale_fill_manual(values = c("CE" = "#00d4ff", "PE" = "#ff3366")) +
  scale_y_continuous(labels = label_number(scale_cut = cut_short_scale())) +
  labs(
    title = "NIFTY 50 Options Open Interest (OI) by Strike Price",
    subtitle = "Analysis of CE vs PE distribution identifying institutional concentration",
    x = "Strike Price (INR)",
    y = "Open Interest (Contracts)",
    fill = "Option Type"
  ) +
  theme_quant() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))

ggsave("results/r_plot1_open_interest.png", plot = p1, width = 10, height = 5, dpi = 300)
message(">> Saved Plot 1: results/r_plot1_open_interest.png")

# 3. Plot 2: Bid-Ask Spread vs Moneyness (Liquidity Decay)
p2 <- ggplot(df, aes(x = moneyness, y = spread, color = option_type)) +
  geom_point(alpha = 0.5, size = 1.8) +
  geom_smooth(method = "loess", se = FALSE, linewidth = 1.2) +
  scale_color_manual(values = c("CE" = "#00d4ff", "PE" = "#ff3366")) +
  geom_vline(xintercept = 1.0, linetype = "dashed", color = "#ffcc00", linewidth = 0.8) +
  annotate("text", x = 1.01, y = max(df$spread, na.rm = TRUE) * 0.9, 
           label = "ATM (Moneyness = 1.0)", color = "#ffcc00", hjust = 0, size = 3.5) +
  labs(
    title = "Bid-Ask Spread Dynamics vs Moneyness Ratio (S / K)",
    subtitle = "Examining market microstructure liquidity decay in OTM vs ATM strikes",
    x = "Moneyness (Spot / Strike)",
    y = "Bid-Ask Spread (INR)",
    color = "Option Type"
  ) +
  theme_quant()

ggsave("results/r_plot2_spread_moneyness.png", plot = p2, width = 10, height = 5, dpi = 300)
message(">> Saved Plot 2: results/r_plot2_spread_moneyness.png")

# 4. Plot 3: Latency Distribution (System Telemetry SLA)
raw_df <- read_csv("data/raw_sample_dataset.csv", show_col_types = FALSE)
p3 <- ggplot(raw_df %>% filter(latency_ms < 5000), aes(x = latency_ms)) +
  geom_histogram(bins = 40, fill = "#38bdf8", color = "#0284c7", alpha = 0.85) +
  geom_vline(aes(xintercept = median(latency_ms, na.rm = TRUE)), 
             color = "#22c55e", linetype = "solid", linewidth = 1) +
  labs(
    title = "WebSocket Protobuf End-to-End Feed Ingestion Latency",
    subtitle = "Hardware & Network SLA Evaluation (< 500ms typical performance)",
    x = "Tick Ingestion Latency (ms)",
    y = "Packet Count"
  ) +
  theme_quant()

ggsave("results/r_plot3_latency.png", plot = p3, width = 10, height = 5, dpi = 300)
message(">> Saved Plot 3: results/r_plot3_latency.png")
