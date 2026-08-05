# PROJECT TITAN — MACHINE LEARNING & REINFORCEMENT LEARNING FOR FOREX

> **Owner:** Principal ML & RL Researchers  
> **Status:** Active — Institutional Knowledge Base v1.0  
> **Target System:** Project TITAN Feature Engineering & Advisory Discovery Pipeline  
> **Integrity Mandate:** Stationarity transformation, Combinatorial Purged Cross-Validation, zero leakage.

---

## 1. Machine Learning Methodologies for FX Time-Series

Applying Machine Learning to foreign exchange requires strict handling of low signal-to-noise ratios, non-stationarity, and regime transitions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TITAN ML ADVISORY FEATURE PIPELINE                       │
└─────────────────────────────────────────────────────────────────────────────┘
  Raw Tick / OHLCV Series ──► [Fractional Differentiation (d ≈ 0.35-0.45)]
                                      │
                                      ▼
  [Feature Matrix] ──► [Purged Group TimeSeries Split / CPCV]
       ├── Technical Indicators (Jesse / TA-Lib)
       ├── Microstructure OFI / VPIN
       └── Macro Yield Curve Spreads & COT Ratios
                                      │
                                      ▼
  [Model Training: TFT / XGBoost / CatBoost / Offline RL]
                                      │
                                      ▼
  [Advisory Feature Weights & Candidate Parameters] ──► (Passed to Gate)
```

---

## 2. Model Architecture Evaluation & Benchmarks

| Model Class | Architecture Strengths | Key Hyperparameters | Overfitting Risk | Target Application |
| :--- | :--- | :--- | :--- | :--- |
| **Temporal Fusion Transformer (TFT)** | Attention mechanisms capture multi-horizon dependencies and macro static covariates | Variable Selection Network, Multi-Head Attention ($H=4$) | High (Requires extensive regularizing dropout) | Multi-horizon volatility and trend forecasting |
| **XGBoost / CatBoost** | Gradient boosted decision trees excel on tabular feature matrices and non-linear interactions | `max_depth=4`, `learning_rate=0.01`, `subsample=0.8` | Moderate | Directional regime classification (Bull/Bear/Range) |
| **Fractionally Differentiated Features** | Preserves maximum historical memory while achieving stationarity (ADF test $p < 0.01$) | Memory threshold $d \in [0.3, 0.5]$ | Low | Input pre-processing for all predictive models |
| **Offline Reinforcement Learning (Implicit Q-Learning / CQL)** | Learns policy from historical trade logs without online environment interaction | Discount $\gamma = 0.99$, Expectile $\tau = 0.7$ | High | Optimal execution slicing & dynamic hedge ratios |

---

## 3. Combinatorial Purged Cross-Validation (CPCV)

Standard $k$-fold cross-validation fails catastrophically on financial time series due to overlap between training and testing labels and autocorrelation.

TITAN mandates **Combinatorial Purged Cross-Validation (Lopez de Prado, 2018)**:
1. **Purging:** Removes training observations whose labels overlap in time with test evaluation periods.
2. **Embargoing:** Removes training samples immediately following a test period to eliminate autoregressive serial correlation leakage.

```
Time ──────────────────────────────────────────────────────────────────►
Fold 1:  [ Train ] ─── [ PURGE ] ─── [ TEST 1 ] ─── [ EMBARGO ] ─── [ Train ]
Fold 2:  [ Train ] ─── [ TEST 2 ] ─── [ EMBARGO ] ─── [ Train ]
```

---

## 4. References & ML Specifications

1. **Lopez de Prado, M. (2018).** *Advances in Financial Machine Learning.* John Wiley & Sons.
2. **Lim, B., Arık, S. Ö., Loeff, N., & Pfister, T. (2021).** Temporal fusion transformers for interpretable multi-horizon time series forecasting. *International Journal of Forecasting*, 37(4), 1374-1389.
3. **Project TITAN Qualification Engine.** [qualification.py](file:///d:/projects/Project%20TITAN/src/titan/research/qualification.py).
