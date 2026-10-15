# Institutional Options Microstructure Analytics & Quantitative Trading Engine

> **Stockezee Options Quant Platform** — An end-to-end institutional algorithmic trading, machine learning execution gating, and derivatives microstructure analysis suite for Indian equity derivatives (NIFTY / BANKNIFTY).

---

## 🏛️ System Architecture

The repository contains a full-stack algorithmic quantitative trading architecture:

```
OPTIONS!!!!!
├── OPTIONS/                       # Quantitative Python Engine
│   ├── market/                    # Real-time L2 Protobuf decoder & NSE scraper
│   ├── opportunities/             # Signal generation, Greek calculations, Alpha models
│   ├── reports/                   # Quantitative reports, PnL analytics, Ideas logs
│   ├── tests/                     # Unit, Integration, Regression & Mutation test suites
│   ├── runner.py                  # Main live trading & backtesting execution engine
│   └── .env.example               # Example credentials template
│
├── stock webpage - Copy/          # Full-Stack Web Platform
│   ├── app/                       # React / Vite / TypeScript trading frontend
│   ├── server/                    # Node.js / Express backend, WebSocket & Supabase routes
│   └── api/                       # REST endpoints & analytics handlers
│
├── master_ml_models_all.R         # R statistical ML benchmark (14 models: XGBoost, RF, GBM, etc.)
├── visulaization.R                # Microstructure, PnL, & performance visualization script
├── presentation_13_ml_models.R    # Presentation-ready ML benchmark scripts
│
├── data/                          # Reference & preprocessed market datasets
│   ├── raw_sample_dataset.csv
│   ├── preprocessed_features_sample.csv
│   └── options_trade_signals_sample.csv
│
├── report_images/                 # System dashboards, architecture diagrams, test metrics
├── pds_review/                    # Review presentations and documentation
│
├── MASTER_PROJECT_SUBMISSION_PORTFOLIO.md   # Complete Capstone Submission Portfolio
├── IEEE_RESEARCH_PAPER_OPTIONS_QUANT_ENGINE.md # Academic IEEE Research Paper
├── DOCUMENT_A_TESTING_AND_DEVELOPMENT_REPORT.md # Testing, CI/CD & Mutation Analysis
├── DOCUMENT_B_PROJECT_DEMO_WALKTHROUGH.md   # Step-by-Step Platform Walkthrough
├── DOCUMENT_C_PROJECT_REPORT_AND_APPENDIX.md # Mathematical Models & Greek Singularity Proofs
└── START_OPTIONS_SYSTEM.bat       # Single-click orchestration launcher
```

---

## 🚀 Key Modules & Capabilities

1. **Microstructure & Order Book Ingestion (`OPTIONS/market`)**
   - High-throughput binary Level-2 Protocol Buffers decoding from Upstox.
   - TLS JA3/JA4 fingerprinting via `curl_cffi` for direct NSE option chain ingestion.
   - Microsecond order book depth analysis, bid-ask spread filters, and toxic flow detection.

2. **Greeks & Adversarial ML Execution Gating (`OPTIONS/opportunities`)**
   - Black-Scholes analytical engine with Vanna, Volga, and Charm cross-derivatives.
   - Half-Kelly sizing, ATR trailing stops, and time-of-day defensive trade blocks.
   - 14 Machine Learning benchmark models evaluated via R (`master_ml_models_all.R`).

3. **Web Dashboard & Execution Gateway (`stock webpage - Copy`)**
   - **Frontend (`app`)**: Real-time options chain viewer, TradingView lightweight charts, signal leaderboards, and demo trading interface.
   - **Backend (`server`)**: Express gateway, Supabase PostgreSQL persistence, Redis pub/sub queue, and AutoTrader webhook router.

---

## 🛠️ Quickstart Guide

### 1. Python Quantitative Engine
```bash
cd OPTIONS
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Fill in your Upstox API credentials in .env

# Run unit & integration tests
pytest tests/

# Start the live execution engine
python runner.py
```

### 2. Full-Stack Web Platform
```bash
cd "stock webpage - Copy"

# Start the Express server
cd server
npm install
cp .env.example .env
# Set Supabase & Redis credentials
npm run dev

# In another terminal, start the React frontend
cd ../app
npm install
npm run dev
```

### 3. One-Click Launcher (Windows)
Double-click `START_OPTIONS_SYSTEM.bat` to launch the data pipeline, backend service, and frontend dashboard simultaneously.

---

## 🧪 Testing & Verification
The platform enforces a four-tier testing framework:
- **Unit Testing**: Black-Scholes partial differential equations and Greek singularity assertions.
- **Integration Testing**: Protobuf ingestion, WebSocket event streams, and Supabase synchronization.
- **Regression Testing**: Temporal lookahead prevention ($t < t + \epsilon$).
- **Mutation Testing**: 88.51% mutant kill rate across dynamic Kelly sizing and defensive risk gates.

---

## 📄 Academic Research & Reports
- [Master Project Submission Portfolio](MASTER_PROJECT_SUBMISSION_PORTFOLIO.md)
- [IEEE Research Paper: Options Quantitative Engine](IEEE_RESEARCH_PAPER_OPTIONS_QUANT_ENGINE.md)
- [Testing & Development Report](DOCUMENT_A_TESTING_AND_DEVELOPMENT_REPORT.md)
- [Project Demo Walkthrough](DOCUMENT_B_PROJECT_DEMO_WALKTHROUGH.md)
- [Mathematical Models & Technical Appendix](DOCUMENT_C_PROJECT_REPORT_AND_APPENDIX.md)
