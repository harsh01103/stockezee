-- ====================================================================================
-- NEXT-GENERATION STOCK RESEARCH ENGINE SCHEMA
-- ====================================================================================

-- 1. SECURITY MASTER
-- Holds the canonical universe of symbols, corporate actions, and mapping data.
CREATE TABLE IF NOT EXISTS public.security_master (
    symbol VARCHAR(50) PRIMARY KEY,
    company_name VARCHAR(255),
    exchange VARCHAR(10) DEFAULT 'NSE',
    instrument_type VARCHAR(20) DEFAULT 'EQUITY',
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap_bucket VARCHAR(50),
    liquidity_bucket VARCHAR(50),
    is_fno_eligible BOOLEAN DEFAULT false,
    listing_date DATE,
    delisting_date DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- 2. DAILY OHLCV
-- EOD historical price data. Partitioning/Hypertables can be added in Supabase.
CREATE TABLE IF NOT EXISTS public.daily_ohlcv (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) REFERENCES public.security_master(symbol),
    date DATE NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume BIGINT,
    traded_value DECIMAL(16, 2),
    delivery_volume BIGINT,
    delivery_percent DECIMAL(5, 2),
    split_ratio DECIMAL(10, 4) DEFAULT 1.0,
    dividend DECIMAL(10, 2) DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    UNIQUE(symbol, date)
);

-- 3. MARKET REGIME
-- Daily state of the broader market (Breadth, Trend, Volatility)
CREATE TABLE IF NOT EXISTS public.market_regime (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL UNIQUE,
    regime_state VARCHAR(50), -- e.g., RISK_ON, RISK_OFF
    nifty_trend_score DECIMAL(5, 2),
    breadth_above_20dma_pct DECIMAL(5, 2),
    breadth_above_50dma_pct DECIMAL(5, 2),
    breadth_above_200dma_pct DECIMAL(5, 2),
    adv_dec_ratio DECIMAL(6, 2),
    volatility_percentile DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- 4. STOCK FEATURES
-- Quant/Technical features calculated during the pipeline runs
CREATE TABLE IF NOT EXISTS public.stock_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) REFERENCES public.security_master(symbol),
    date DATE NOT NULL,
    rs_1w DECIMAL(10, 4),
    rs_1m DECIMAL(10, 4),
    rs_3m DECIMAL(10, 4),
    rs_6m DECIMAL(10, 4),
    residual_momentum DECIMAL(10, 4),
    atr_20 DECIMAL(10, 2),
    volatility_contraction_score DECIMAL(5, 2),
    cmf_20 DECIMAL(5, 2),
    trend_quality_score DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    UNIQUE(symbol, date)
);

-- 5. ANALYSIS RUNS
-- Job tracking for the nightly pipeline
CREATE TABLE IF NOT EXISTS public.analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    start_time TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    end_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'RUNNING',
    current_stage VARCHAR(50),
    universe_size INTEGER,
    candidates_remaining INTEGER,
    model_version VARCHAR(50),
    errors JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- 6. COMPANY DOCUMENTS
-- Stores document metadata for NLP/DocIntel
CREATE TABLE IF NOT EXISTS public.company_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) REFERENCES public.security_master(symbol),
    origin_type VARCHAR(50) NOT NULL, -- FILING, NEWS, PRESENTATION, ANNUAL_REPORT
    source_url TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    retrieval_score NUMERIC(10, 4) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- 7. EXTRACTED FACTS
-- Relational structured facts (e.g. QoQ Revenue, Order Wins)
CREATE TABLE IF NOT EXISTS public.extracted_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) REFERENCES public.security_master(symbol),
    document_id UUID REFERENCES public.company_documents(id),
    metric VARCHAR(100),
    value VARCHAR(255),
    unit VARCHAR(50),
    period VARCHAR(50),
    evidence_date DATE NOT NULL,
    source_url TEXT,
    confidence DECIMAL(3, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- 8. CHART ANNOTATIONS
-- Stores JSON shapes for the UI (rectangles, markers, lines)
CREATE TABLE IF NOT EXISTS public.chart_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) REFERENCES public.security_master(symbol),
    run_id UUID REFERENCES public.analysis_runs(id),
    date DATE NOT NULL,
    annotations JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- 9. TRADE PLANS (FINAL RECOMMENDATIONS)
-- The output of the pipeline
CREATE TABLE IF NOT EXISTS public.trade_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES public.analysis_runs(id),
    symbol VARCHAR(50) REFERENCES public.security_master(symbol),
    date DATE NOT NULL,
    setup_type VARCHAR(100),
    opportunity_score DECIMAL(5, 2),
    trade_readiness VARCHAR(50),
    entry_trigger DECIMAL(10, 2),
    entry_high DECIMAL(10, 2),
    stop_loss DECIMAL(10, 2),
    target_1 DECIMAL(10, 2),
    target_2 DECIMAL(10, 2),
    risk_reward DECIMAL(5, 2),
    expected_horizon VARCHAR(50),
    confidence DECIMAL(3, 2),
    thesis JSONB, -- Explainability facts (Why, Risks, Confirmation)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_daily_ohlcv_symbol ON public.daily_ohlcv(symbol);
CREATE INDEX IF NOT EXISTS idx_daily_ohlcv_date ON public.daily_ohlcv(date);
CREATE INDEX IF NOT EXISTS idx_stock_features_symbol ON public.stock_features(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_features_date ON public.stock_features(date);
CREATE INDEX IF NOT EXISTS idx_trade_plans_date ON public.trade_plans(date);
