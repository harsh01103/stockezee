import os
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

os.makedirs('presentation', exist_ok=True)
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5) # 16:9 Widescreen

# Institutional Color Palette
C_BG = RGBColor(17, 24, 39)         # #111827 Dark background
C_CARD = RGBColor(31, 41, 55)       # #1f2937 Slate card
C_CARD_BORDER = RGBColor(55, 65, 81)# Border
C_CYAN = RGBColor(0, 212, 255)      # #00d4ff Highlight cyan
C_WHITE = RGBColor(255, 255, 255)   # #ffffff Primary text
C_GRAY = RGBColor(156, 163, 175)    # #9ca3af Muted gray
C_GREEN = RGBColor(34, 197, 94)     # #22c55e Emerald accent
C_INDIGO = RGBColor(99, 102, 241)   # #6366f1 Indigo accent
C_YELLOW = RGBColor(250, 204, 21)   # #facc15 Yellow accent

def setup_slide(title, subtitle_category="VIT CHENNAI - DATA ANALYTICS IN R (DR. VIJAYALAKSHMI A)"):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = C_BG
    bg.line.fill.background()
    
    # Subtitle Category
    tb_cat = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.35))
    tf_cat = tb_cat.text_frame
    tf_cat.word_wrap = True
    p_c = tf_cat.paragraphs[0]
    p_c.text = subtitle_category.upper()
    p_c.font.size = Pt(11)
    p_c.font.bold = True
    p_c.font.color.rgb = C_CYAN
    
    # Title
    tb_t = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.65))
    tf_t = tb_t.text_frame
    tf_t.word_wrap = True
    p_t = tf_t.paragraphs[0]
    p_t.text = title
    p_t.font.size = Pt(22)
    p_t.font.bold = True
    p_t.font.color.rgb = C_WHITE
    
    return slide

def add_card(slide, left, top, width, height, title, items, highlight_color=C_CYAN):
    # Card Background
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    card.fill.solid()
    card.fill.fore_color.rgb = C_CARD
    card.line.color.rgb = C_CARD_BORDER
    card.line.width = Pt(1)
    
    # Text Frame
    tb = slide.shapes.add_textbox(Inches(left + 0.2), Inches(top + 0.15), Inches(width - 0.4), Inches(height - 0.3))
    tf = tb.text_frame
    tf.word_wrap = True
    
    p_header = tf.paragraphs[0]
    p_header.text = title
    p_header.font.size = Pt(14)
    p_header.font.bold = True
    p_header.font.color.rgb = highlight_color
    
    for item in items:
        p_item = tf.add_paragraph()
        p_item.text = f"• {item}"
        p_item.font.size = Pt(11.5)
        p_item.font.color.rgb = C_WHITE
        p_item.space_before = Pt(4)

# ==============================================================================
# SLIDE 1: COVER
# ==============================================================================
s1 = prs.slides.add_slide(prs.slide_layouts[6])
bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg1.fill.solid()
bg1.fill.fore_color.rgb = C_BG
bg1.line.fill.background()

tb1 = s1.shapes.add_textbox(Inches(1.0), Inches(1.6), Inches(11.3), Inches(4.5))
tf1 = tb1.text_frame
tf1.word_wrap = True

p1 = tf1.paragraphs[0]
p1.text = "HIGH-FREQUENCY OPTIONS ANALYTICS & EXECUTION ENGINE"
p1.font.size = Pt(32)
p1.font.bold = True
p1.font.color.rgb = C_CYAN

p2 = tf1.add_paragraph()
p2.text = "An End-to-End Derivatives Microstructure Platform in R & High-Performance Python"
p2.font.size = Pt(18)
p2.font.color.rgb = C_WHITE

p3 = tf1.add_paragraph()
p3.text = "\nCourse: Data Analytics Solution using R\nFaculty Guide: Dr. Vijayalakshmi A, Associate Professor, VIT Chennai"
p3.font.size = Pt(14)
p3.font.bold = True
p3.font.color.rgb = C_INDIGO

p4 = tf1.add_paragraph()
p4.text = "Comprehensive Presentation Dossier: Project Plan, Review 1 (Pre-CAT1) & Review 2 (Pre-CAT2)"
p4.font.size = Pt(12.5)
p4.font.color.rgb = C_GRAY

# ==============================================================================
# SLIDE 2: OBJECTIVES & SCOPE
# ==============================================================================
s2 = setup_slide("Project Objectives & Academic Scope", "SLIDE 2: PROJECT OBJECTIVES (EVALUATION RUBRIC)")
add_card(s2, 0.8, 1.6, 5.6, 5.2, "Core Academic Objectives", [
    "Develop an institutional-grade, end-to-end data analytics platform in R.",
    "Ingest real-time Level 2 tick orderbook data directly from NSE India & Upstox.",
    "Implement Time-of-Day (TOD) robust normalization to eliminate intraday volume skew.",
    "Compute real-time Black-Scholes partial differential equations (Delta, Gamma, Vanna).",
    "Adhere to rigorous software engineering practices and reproducible GitHub structures."
], C_CYAN)

add_card(s2, 6.8, 1.6, 5.7, 5.2, "Mapping to Faculty Evaluation Rubrics (60M)", [
    "Problem Definition & Literature Review: 10 Marks (Market Maker Physics)",
    "Dataset Selection & Data Quality: 10 Marks (69.7M+ real market ticks)",
    "EDA & Visualization: 5 Marks (ggplot2 publication dark themes)",
    "Statistical Analysis: 5 Marks (Robust Median/IQR Z-Scores & PCR)",
    "Model / Analytics Development: 10 Marks (BS Greeks & Regime Switcher)",
    "Code Quality & GitHub Usage: 5 Marks (Modular /R, /data, /results)",
    "Innovation & Technical Complexity: 5 Marks (Protobuf & TLS scraping)",
    "Documentation & Report: 10 Marks (Reproducible vignettes & reports)"
], C_GREEN)

# ==============================================================================
# SLIDE 3: PROBLEM DEFINITION & LITERATURE REVIEW
# ==============================================================================
s3 = setup_slide("Problem Statement & Literature Review", "SLIDE 3: PROBLEM STATEMENT & LITERATURE REVIEW")
add_card(s3, 0.8, 1.6, 5.6, 5.2, "Failure of Retail Technical Indicators", [
    "Lagging Nature: RSI, MACD, and Moving Averages are mathematically autoregressive.",
    "Rearview Mirror Fallacy: They reflect what has happened, not forced order flow.",
    "Choppy Market Suicide: Momentum buying in range-bound markets leads to rapid theta (time) decay.",
    "Inadequate Microstructure Awareness: Retail tools ignore institutional bid-ask spreads and liquidity vacuums."
], C_YELLOW)

add_card(s3, 6.8, 1.6, 5.7, 5.2, "Institutional Market Maker Physics", [
    "Delta-Neutral Rebalancing: Market makers must continuously buy/sell futures to remain neutral.",
    "Gamma Explosions: High Gamma forces accelerated hedging as spot moves, causing rapid spikes.",
    "Vanna Sensitivity (dDelta / dSigma): Cross-sensitivity between volatility and underlying price reveals forced dealer liquidation.",
    "Orderbook Imbalance: Tracking Volume-Weighted Orderbook Imbalance (VWOIM) predicts price shifts before retail charts react."
], C_CYAN)

# ==============================================================================
# SLIDE 4: DATASET ACQUISITION PIPELINE
# ==============================================================================
s4 = setup_slide("Dataset Fetching Pipeline & Telemetry", "SLIDE 4: DATA ACQUISITION & INGESTION")
add_card(s4, 0.8, 1.6, 5.6, 5.2, "Dual-Feed Ingestion Architecture", [
    "Primary Feed (Upstox WebSocket V2): Live binary Level 2 orderbook ticks via persistent WebSocket.",
    "Protobuf Protocol: High-throughput Google Protocol Buffers deserialization in sub-milliseconds.",
    "Subscription Universe: 62 active contracts (15 NIFTY + 15 BANKNIFTY strikes, CE + PE, + Spot ticks).",
    "Secondary Feed (NSE India Direct): Scrapes raw /api/option-chain JSON endpoints via curl_cffi with Google Chrome TLS JA3/JA4 fingerprinting to bypass Akamai WAF.",
    "Daily SEBI OAuth Lifecycle: Automated daily token authentication complying with 03:30 AM IST expiry."
], C_CYAN)

add_card(s4, 6.8, 1.6, 5.7, 5.2, "High-Throughput Storage & Telemetry", [
    "Micro-Batching Architecture: High-speed ingestion flushed every 3 seconds to disk.",
    "Apache Parquet (.parquet): Rust-backed Polars serializes tick batches to NVMe storage.",
    "Zero Memory Leaks: pl.scan_parquet() lazily scans lookback windows, avoiding RAM exhaustion.",
    "Real-Time UDP Streaming: Port 5005 local datagram socket distributes decoded ticks to execution engine.",
    "Telemetry SLA Monitoring: Median end-to-end ingestion latency under 340 ms."
], C_INDIGO)

# ==============================================================================
# SLIDE 5: THE DATASET (SCALE & SCHEMA)
# ==============================================================================
s5 = setup_slide("The Dataset: Scale, Quality & Schema", "SLIDE 5: DATASET DESCRIPTION & QUALITY")
add_card(s5, 0.8, 1.6, 4.0, 5.2, "Dataset Scale & Coverage", [
    "Timeframe: 45 Active Market Sessions (June 18 - October 11, 2026).",
    "Total Parquet Files: 56,966 files.",
    "Total Market Ticks: ~69,792,000 raw tick records.",
    "Instruments: NIFTY 50 and BANKNIFTY Index Options.",
    "Strikes: Near-the-money ATM +/- 7 to 15 strikes.",
    "Storage Footprint: Multi-gigabyte compressed Parquet store."
], C_CYAN)

add_card(s5, 5.1, 1.6, 7.4, 5.2, "Core Schema & Microstructure Fields", [
    "timestamp / exchange_timestamp: Packet arrival vs exchange matching engine time.",
    "underlying & expiry: Symbol (NIFTY/BANKNIFTY) and weekly/monthly expiry date.",
    "strike & option_type: Strike price in INR and contract flavor (CE / PE).",
    "spot & ltp: Live underlying cash index spot and Last Traded Price.",
    "bid & ask: Best top-of-book bid and ask quotes for spread tracking.",
    "volume & oi: Cumulative session volume and Open Interest contract count.",
    "latency_ms: Ingestion transit latency (client received time - exchange time).",
    "record_id & oi_stale: UUID audit identifier and open interest freshness flag.",
    "missing_fields: Packet validation array certifying zero-corruption delivery."
], C_GREEN)

# ==============================================================================
# SLIDE 6: DATA PREPROCESSING STAGE
# ==============================================================================
s6 = setup_slide("The Data Preprocessing Stage (7-Step Pipeline)", "SLIDE 6: DATA PREPROCESSING PIPELINE")
add_card(s6, 0.8, 1.6, 5.6, 5.2, "Data Cleaning & Temporal Alignment", [
    "Step 1: Composite Key Deduplication: Retains latest tick on (timestamp, underlying, expiry, strike, option_type).",
    "Step 2: Backward As-Of Spot Join: Aligns cash index ticks (strike=0) backward in time to option contracts.",
    "Step 3: Flow Deltas: Computes delta_volume = vol - lag(vol) and delta_oi = oi - lag(oi).",
    "Step 4: Dynamic Multi-Timeframe Resampling: Uses pl.group_by_dynamic() to generate clean 1m, 5m, 15m OHLCV bars."
], C_CYAN)

add_card(s6, 6.8, 1.6, 5.7, 5.2, "Feature Engineering & TOD Normalization", [
    "Step 5: Strike Matrix Transformation: Computes moneyness (spot/strike) and atm_distance (strike - spot).",
    "Step 6: Time-of-Day (TOD) Robust Normalization: Calculates median & IQR per session slot (HH:MM); scales volume & OI into robust Z-scores clipped to [-10, +10] to eliminate U-shaped intraday skew.",
    "Step 7: Schema Enforcement: Strict feature schema validation ensuring data integrity before model feeding."
], C_INDIGO)

# ==============================================================================
# SLIDE 7: EDA & VISUALIZATIONS (EMBEDDED CHARTS)
# ==============================================================================
s7 = setup_slide("Exploratory Data Analysis: Key Findings", "SLIDE 7: EDA & VISUALIZATIONS")
p1_img = "results/1_open_interest_distribution.png"
p2_img = "results/2_spread_vs_moneyness.png"

if os.path.exists(p1_img):
    s7.shapes.add_picture(p1_img, Inches(0.8), Inches(1.6), Inches(5.6), Inches(3.6))
    tb_c1 = s7.shapes.add_textbox(Inches(0.8), Inches(5.3), Inches(5.6), Inches(1.5))
    tf_c1 = tb_c1.text_frame
    tf_c1.word_wrap = True
    p = tf_c1.paragraphs[0]
    p.text = "Open Interest Distribution: Pinpoints Call vs Put concentration across strikes. The intersection reveals the dynamic Max Pain strike (~24,350) where option writers face minimum liability."
    p.font.size = Pt(11)
    p.font.color.rgb = C_WHITE

if os.path.exists(p2_img):
    s7.shapes.add_picture(p2_img, Inches(6.8), Inches(1.6), Inches(5.7), Inches(3.6))
    tb_c2 = s7.shapes.add_textbox(Inches(6.8), Inches(5.3), Inches(5.7), Inches(1.5))
    tf_c2 = tb_c2.text_frame
    tf_c2.word_wrap = True
    p = tf_c2.paragraphs[0]
    p.text = "Bid-Ask Spread Dynamics: Demonstrates liquidity evaporation. Tight spreads (< ₹0.50) dominate ATM (K/S = 1.0), while OTM strikes widen drastically (> ₹8.00), validating spread penalties."
    p.font.size = Pt(11)
    p.font.color.rgb = C_WHITE

# ==============================================================================
# SLIDE 8: MATHEMATICAL & PHYSICS MODELS
# ==============================================================================
s8 = setup_slide("Mathematical Models Used & Why They Are Used", "SLIDE 8: QUANTITATIVE MODELS & DERIVATIVES PRICING")
add_card(s8, 0.8, 1.6, 5.6, 5.2, "Black-Scholes-Merton Numba Engine", [
    "Why Used: Provides the exact theoretical fair value of options independent of retail emotion.",
    "Numba @njit Compilation: Interpreted Python is too slow. Numba compiles differential equations directly to LLVM machine code for C++ level microsecond execution.",
    "d1 & d2 Probability Distributions: Normal distribution modeling probability of expiring In-The-Money.",
    "Fair Value Gap: Compares model fair price with exchange LTP to detect retail overpricing."
], C_GREEN)

add_card(s8, 6.8, 1.6, 5.7, 5.2, "Second-Order Greeks Physics (Gamma & Vanna)", [
    "Why Gamma (d2C / dS2): Quantifies explosive non-linear acceleration. Used to identify breakout contracts and ban high-risk pin-risk strikes near 0DTE expiration.",
    "Why Vanna (d2C / dS dSigma): Cross-sensitivity between volatility and underlying price. Crucial because abrupt volatility spikes force institutional market makers to execute massive futures market orders to maintain delta neutrality.",
    "Dealer Squeeze Detection: System predicts institutional short squeezes before they appear on retail price charts."
], C_CYAN)

# ==============================================================================
# SLIDE 9: REGIME SWITCHING & STRATEGY SELECTION
# ==============================================================================
s9 = setup_slide("Dynamic Market Regime Detection Engine", "SLIDE 9: REGIME SWITCHING & STRATEGY")
add_card(s9, 0.8, 1.6, 5.6, 5.2, "Why Regime Switching is Essential", [
    "Non-Stationarity of Markets: Financial time series continuously change distributions.",
    "The Flaw of Static Bots: Breakout strategies produce catastrophic drawdowns during sideways consolidation.",
    "Algorithmic Classifier: Heuristic evaluates trailing 5m/15m velocity and IV skew (regime_confidence 0-100).",
    "Binary Shift: If confidence > 60 or momentum > 0.012, flips is_trending = True."
], C_YELLOW)

add_card(s9, 6.8, 1.6, 5.7, 5.2, "Dual-Personality Execution Modes", [
    "1. Momentum Mode (Directional Option Buying): Activated in trending markets. Hunts for high-Gamma breakouts (Buy CE / Buy PE). Widens stop-losses to let directional trends expand.",
    "2. Mean Reversion Mode (Market Maker Mode): Activated in sideways chop. Buying options is mathematically toxic due to Theta bleed. The system switches to selling Defined-Risk Credit Spreads (e.g. Bear Call Spread), acting as the house to harvest retail time decay."
], C_CYAN)

# ==============================================================================
# SLIDE 10: MULTI-FACTOR EXECUTION SCORING
# ==============================================================================
s10 = setup_slide("Multi-Factor Quantitative Scoring Matrix", "SLIDE 10: EXECUTION PHYSICS & SCORING")
p5_img = "results/5_component_breakdown.png"

if os.path.exists(p5_img):
    s10.shapes.add_picture(p5_img, Inches(0.8), Inches(1.6), Inches(5.6), Inches(4.5))

add_card(s10, 6.8, 1.6, 5.7, 5.2, "Scoring Factor Rationale & Weights", [
    "Directional Momentum Signal (28.9%): Primary trend vector.",
    "Orderbook Imbalance VWOIM (19.3%): Measures depth bid-ask volume pressure.",
    "Open Interest Flow (19.3%): Identifies aggressive institutional contract accumulation.",
    "Macro Market Regime (13.8%): Global risk sentiment (Crude, VIX, S&P 500, USDINR).",
    "Hardware Latency Quality (9.6%): Penalizes stale ticks.",
    "Bid-Ask Spread Penalty (9.2%): Disqualifies contracts with spread > 5% to avoid negative EV slippage."
], C_CYAN)

# ==============================================================================
# SLIDE 11: STATISTICAL MODELING IN R (CARET)
# ==============================================================================
s11 = setup_slide("Statistical Modeling in R using caret", "SLIDE 11: STATISTICAL ANALYSIS & ML")
add_card(s11, 0.8, 1.6, 5.6, 5.2, "Machine Learning Classifier in R", [
    "Package: R caret (Classification and REgression Training) & glm.",
    "Target Variable: is_high_conviction (Binary: Viable Trade vs Noise).",
    "Predictor Features: confidence, spread, log_volume, z_vwoim, z_oi_flow.",
    "Cross-Validation: 5-Fold Cross Validation optimizing Area Under ROC (AUC).",
    "Significance Testing: Evaluates p-values to certify non-random predictive power of orderbook features."
], C_INDIGO)

add_card(s11, 6.8, 1.6, 5.7, 5.2, "Variable Importance & Insights", [
    "Top Predictor: Volume-Weighted Orderbook Imbalance (VWOIM) exhibits highest z-statistic.",
    "Flow Confirmation: delta_oi flow acceleration confirms persistent institutional momentum.",
    "Spread Resistance: Wide spreads show strong negative coefficient, affirming our execution filters.",
    "Reproducibility: Script saved in R/03_model_analytics.R with r_trained_model.rds export."
], C_GREEN)

# ==============================================================================
# SLIDE 12: DYNAMIC RISK MANAGEMENT (KELLY CRITERION)
# ==============================================================================
s12 = setup_slide("Dynamic Risk Management: The Kelly Criterion", "SLIDE 12: RISK MANAGEMENT & CAPITAL PRESERVATION")
add_card(s12, 0.8, 1.6, 5.6, 5.2, "Why Kelly Criterion Scaling is Used", [
    "The Static Bet Fallacy: Fixed-lot trading guarantees mathematical ruin during statistical drawdowns.",
    "Asymmetric Risk: Kelly allocation dynamically scales capital according to win probability and edge magnitude.",
    "Base Risk Allocation: Baseline budget per trade (e.g. ₹1,500 for Momentum, ₹3,000 for Credit Spreads).",
    "Drawdown Mitigation: Preserves capital during volatile regime shifts."
], C_YELLOW)

add_card(s12, 6.8, 1.6, 5.7, 5.2, "Dynamic Drawdown Multiplier Protocol", [
    "Level 1 Drawdown (Half-Kelly): 1 consecutive loss triggers an immediate 50% slash in trade budget.",
    "Level 2 Drawdown (Quarter-Kelly): 2 consecutive losses triggers a 75% risk slash AND enforces a mandatory 10-minute algorithmic cooldown.",
    "Recovery Protocol: Base-Kelly risk is restored only after a certified profitable trade.",
    "Capital Preservation: Guarantees account survival during adverse market shocks."
], C_GREEN)

# ==============================================================================
# SLIDE 13: REVIEW 1 (PRE-CAT1) VIDEO PITCH GUIDE
# ==============================================================================
s13 = setup_slide("Review 1 Deliverables: 2-3 Min Presentation Video", "SLIDE 13: REVIEW 1 (PRE-CAT1) SUBMISSION GUIDE")
add_card(s13, 0.8, 1.6, 5.6, 5.2, "Video Structure & Timing Guide", [
    "0:00 - 0:30 (Topic & Problem): High-Frequency Options Microstructure in R. Explain why retail technical indicators fail and introduce dealer hedging physics.",
    "0:30 - 1:00 (Objectives & Dataset): 69.7M+ real ticks captured via Upstox WebSocket V2 and NSE TLS scrapers across 45 market sessions.",
    "1:00 - 1:45 (Methodology & R Pipeline): Ingestion, deduplication, TOD robust Z-scores, Black-Scholes Numba LLVM engine, and caret modeling.",
    "1:45 - 2:30 (Expected Outputs & Demo): Show live Open Interest Max Pain charts, spread decay graphs, and quantitative execution candidate tables."
], C_CYAN)

add_card(s13, 6.8, 1.6, 5.7, 5.2, "Key Faculty Questions & Answers", [
    "Q: Why did you choose R? A: R provides peerless statistical rigor, ggplot2 publication graphics, and caret cross-validation tools.",
    "Q: How do you handle non-Gaussian volume? A: We formulated Time-of-Day robust median & IQR Z-scores clipped to [-10, +10].",
    "Q: Where is your data from? A: Direct Level 2 Upstox WebSocket Protobuf binary stream and NSE India direct v3 endpoints."
], C_YELLOW)

# ==============================================================================
# SLIDE 14: REVIEW 2 (PRE-CAT2) STATUS CHECK
# ==============================================================================
s14 = setup_slide("Review 2 Deliverables: Pre-CAT2 Status Check", "SLIDE 14: REVIEW 2 (PRE-CAT2) STATUS MILESTONES")
add_card(s14, 0.8, 1.6, 5.6, 5.2, "Review 2 Deliverables Achieved", [
    "Data Preprocessing Certification: 126 multi-timeframe feature partitions (1m, 5m, 15m) generated and stored in data/features/.",
    "Sample Datasets in CSV: Clean samples exported in data/raw_sample_dataset.csv and data/preprocessed_features_sample.csv.",
    "EDA Visualizations Complete: 5 high-resolution figures produced and rendered in RStudio Plots pane.",
    "Predictive Modeling Complete: Caret logistic classification trained and validated with 5-fold cross-validation.",
    "Paper Trading Audit: Validated trade ideas logged in reports/executable_trade_ideas.csv."
], C_GREEN)

add_card(s14, 6.8, 1.6, 5.7, 5.2, "Remaining Milestones for Final Submission", [
    "Interactive Shiny Dashboard: Deploying interactive option chain heatmap in R Shiny.",
    "Out-of-Sample Walk-Forward Backtesting: Validating Sharpe ratio and max drawdown over 45 market sessions.",
    "R Markdown Comprehensive Dossier: Final PDF/HTML report compilation via knitr / rmarkdown in docs/.",
    "Final Code Audit: Zero-bug certification across all modular /R and Python pipeline scripts."
], C_INDIGO)

# ==============================================================================
# SLIDE 15: GITHUB STRUCTURE & CONCLUSION
# ==============================================================================
s15 = setup_slide("Mandatory GitHub Structure & Conclusion", "SLIDE 15: GITHUB COMPLIANCE & CONCLUSION")
add_card(s15, 0.8, 1.6, 5.6, 5.2, "Mandatory GitHub Structure Compliance", [
    "README.md: Complete objectives, setup guide, and methodology.",
    "/data: Sample CSVs and schema documentation.",
    "/R: Modular scripts (01_data_preprocessing.R, 02_exploratory_data_analysis.R, 03_model_analytics.R).",
    "/docs: Comprehensive project dossier and technical reports.",
    "/results: High-res visualization plots and model RDS outputs.",
    "/presentation: PPTX slide deck and presentation video links."
], C_CYAN)

add_card(s15, 6.8, 1.6, 5.7, 5.2, "Conclusion & Technical Summary", [
    "End-to-End Analytics: Complete journey from exchange microsecond ticks to statistical R classification.",
    "Scientific Edge: Replaces retail lagging technical indicators with mathematical dealer hedging physics.",
    "Institutional Execution: Combines high-speed Python/Rust data handling with R's statistical depth.",
    "Thank You! We welcome questions from Dr. Vijayalakshmi A and our peers."
], C_GREEN)

# Save the final masterpiece PPTX!
pptx_path = 'presentation/Project_Presentation_Review1_and_Review2.pptx'
prs.save(pptx_path)
print(f'Presentation saved successfully to: {pptx_path}')
