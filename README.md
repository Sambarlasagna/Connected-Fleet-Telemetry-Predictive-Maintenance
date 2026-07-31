# 🚗 Fleet Predictive Analytics — Predictive Maintenance with PySpark

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![PySpark](https://img.shields.io/badge/Apache_Spark-3.5-orange?logo=apachespark)
![Scikit](https://img.shields.io/badge/Spark_MLlib-RandomForest-brightgreen)
![Status](https://img.shields.io/badge/Status-Complete-success)

> **An end-to-end distributed ML pipeline that predicts engine component failures 24 hours in advance using real vehicle telemetry data — achieving AUC-ROC of 0.97 and an estimated 87% reduction in unplanned fleet maintenance costs.**

---

## 📌 Problem Statement

Connected vehicle fleets generate continuous streams of sensor telemetry (voltage, rotation, pressure, vibration) from hundreds of machines. Reactive maintenance — fixing components *after* failure — is expensive and causes unplanned downtime.

This project builds a **predictive maintenance pipeline** that:
- Processes 876,000 rows of hourly sensor telemetry using **Apache Spark (PySpark)**
- Engineers time-series rolling-window features to capture sensor drift
- Trains a **Spark MLlib Random Forest** to predict failure within the next 24 hours
- Quantifies real-world business impact in terms of fleet cost savings

---

## 🏗️ Pipeline Architecture

```
Raw CSVs (5 files)
│
│  PdM_telemetry.csv   ← 876,100 rows of hourly sensor readings
│  PdM_failures.csv    ← 761 recorded failure events
│  PdM_errors.csv      ← 3,919 error log entries
│  PdM_machines.csv    ← 100 machines (model + age metadata)
│  PdM_maint.csv       ← 3,286 maintenance records
│
▼
[ 01_eda.ipynb ] — Exploratory Data Analysis
│   Sensor distributions, failure trends, fleet metadata analysis
│
▼
[ 02_spark_pipeline.ipynb ] — Distributed Feature Engineering (PySpark)
│   ├── Timestamp casting & null audit
│   ├── Rolling Window Features (3h + 24h mean & std per sensor) → +16 features
│   ├── Error code aggregation (one-hot counts per machine/hour) → +5 features
│   ├── Fleet metadata join (model type, vehicle age)            → +2 features
│   └── Binary label: failure within next 24h (broadcast join)
│
▼
[ 03_predictive_model.ipynb ] — ML Training & Evaluation (Spark MLlib)
    ├── Class balancing (4:1 undersample negatives)
    ├── VectorAssembler + StandardScaler pipeline
    ├── Chronological train/test split (no data leakage)
    ├── Random Forest (100 trees, depth 8)
    └── Business cost-impact analysis
```

---

## 📊 Results

### Model Performance

| Metric     | Score  |
|------------|--------|
| AUC-ROC    | **0.9714** |
| AUC-PR     | **0.8413** |
| F1 Score   | **0.9370** |
| Accuracy   | **0.9356** |
| Recall     | **0.9356** |
| Precision  | **0.9400** |

### Confusion Matrix (Test Set)

|                    | Predicted Normal | Predicted Failure |
|--------------------|-----------------|-------------------|
| **Actual Normal**  | 13,751 ✅        | 801 ⚠️             |
| **Actual Failure** | 358 ❌           | 3,080 ✅           |

> The model catches **89.6% of all real failures** with only a **5.5% false alarm rate** — a strong operational trade-off given that a missed failure costs ~42× more than a false alarm.

### Business Cost Impact

| Scenario                        | Estimated Cost   |
|---------------------------------|-----------------|
| Reactive maintenance (no model) | $29,223,000     |
| With predictive model           | $3,659,000      |
| **Estimated savings**           | **$25,564,000 (87%)** |

### Top Feature Importances

| Rank | Feature             | Importance |
|------|---------------------|------------|
| 1    | `rotate_mean24h`    | 0.2068     |
| 2    | `volt_mean24h`      | 0.1584     |
| 3    | `vibration_mean24h` | 0.1243     |
| 4    | `rotate_mean3h`     | 0.1122     |
| 5    | `pressure_mean24h`  | 0.0758     |

> **Key insight:** 24-hour rolling *means* (not instantaneous readings) dominate feature importance — confirming that gradual sensor drift over time is more predictive of failure than any individual spike.

---

## 🛠️ Tech Stack

| Layer               | Technology                          |
|---------------------|-------------------------------------|
| Distributed compute | Apache Spark 3.5 (PySpark)          |
| ML framework        | Spark MLlib (Pipeline API)          |
| Feature engineering | Spark Window Functions              |
| EDA & visualization | Pandas, Matplotlib, Seaborn         |
| Data format         | CSV (raw) → Parquet (processed)     |
| Environment         | Python 3.12, Jupyter Notebook       |

---

## 📁 Project Structure

```
Connected-Fleet-Telemetry-Predictive-Maintenance/
│
├── notebooks/
│   ├── 01_eda.ipynb                  # Exploratory Data Analysis
│   ├── 02_spark_pipeline.ipynb       # PySpark feature engineering
│   └── 03_predictive_model.ipynb     # Spark MLlib model training & evaluation
│
├── data/
│   ├── raw/                          # Source CSVs (not tracked in git)
│   └── processed/                    # Engineered Parquet dataset
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🚀 How to Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Download the dataset
Get the [Microsoft Azure Predictive Maintenance Dataset](https://www.kaggle.com/datasets/arnabbiswas1/microsoft-azure-predictive-maintenance) from Kaggle and place all 5 CSV files in `data/raw/`.

### 3. Run the notebooks in order
```bash
jupyter notebook
```
Open and run:
1. `01_eda.ipynb`
2. `02_spark_pipeline.ipynb`
3. `03_predictive_model.ipynb`

---

## 🔍 Key Engineering Decisions

**Why chronological train/test split?**
Random splits cause data leakage in time-series data — the model would train on future data to predict the past. A chronological 80/20 split ensures evaluation reflects real deployment conditions.

**Why broadcast join for labels?**
The failures table has only 761 rows. Broadcasting it to all Spark executors avoids a full shuffle-join against 876k telemetry rows, making label creation ~10× more memory efficient.

**Why undersample instead of oversample?**
Oversampling (SMOTE) on Spark requires UDFs which are slow. 4:1 undersampling of the majority class achieves class balance while keeping the dataset fully within JVM operations.

---

## 📈 Production Next Steps

- **Real-time streaming:** Deploy via Kafka + Spark Structured Streaming to evaluate each machine's sensor batch as it arrives and trigger maintenance alerts
- **Model serving:** Export via MLflow and serve predictions via a REST API
- **Drift monitoring:** Track sensor distribution shifts over time to detect model degradation

---

## 👤 Author

**Jayashuriya J** — [GitHub](https://github.com/Sambarlasagna)
