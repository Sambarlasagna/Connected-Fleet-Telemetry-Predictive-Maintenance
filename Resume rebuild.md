# ML Portfolio — 3 Flagship Projects

## 🎯 Goal

Build a **3-project ML portfolio** where each project demonstrates a different part of the modern ML stack instead of having several projects overlap.

The portfolio should collectively demonstrate:

- Machine Learning
    
- Deep Learning / Neural Networks
    
- Computer Vision
    
- NLP / LLMs / RAG
    
- Big Data
    
- PySpark / Apache Spark
    
- Complete data pipelines
    
- Streaming with Kafka
    
- Workflow orchestration with Airflow
    
- MLOps with MLflow
    
- Docker
    
- Kubernetes
    
- Prometheus + Grafana
    
- Infrastructure as Code with Terraform
    
- AWS / Cloud
    
- FastAPI / production deployment
    

The goal is **not** to put every technology into every project.

Instead:

> **Each project should have a clear purpose and collectively cover the entire ML lifecycle.**

---

# 📊 Current Portfolio

|Project|Main Focus|Current Strength|
|---|---|---|
|**Connected Fleet Telemetry**|Big Data + Classical ML|🟢 Strong|
|**End-to-End Autonomous Steering**|Deep Learning + Computer Vision|🟢 Strong|
|**AutoNotes-Pro**|LLM + RAG|🟢 Strong|
|**CineScope**|NLP + MLOps|🟢 Good|

Current resume already demonstrates PySpark, PyTorch, TensorFlow, Scikit-Learn, LLM/RAG, ChromaDB, Sentence Transformers, MLflow, Docker, Kubernetes, Prometheus and Grafana. However, several of these are currently demonstrated only in the Skills section rather than across projects.

---

# ⚠️ Main Problem

The projects are individually good, but there is some overlap.

For example:

### End-to-End Steering

```text
Images
   ↓
Preprocessing
   ↓
Augmentation
   ↓
CNN
   ↓
Steering Prediction
```

### CineScope

```text
Text
   ↓
NLP preprocessing
   ↓
CNN / LSTM
   ↓
Sentiment Prediction
```

Both demonstrate neural networks.

The problem isn't that using CNN twice is inherently bad.

The bigger problem is:

> **The portfolio doesn't yet strongly demonstrate production-scale ML infrastructure, cloud deployment, streaming, orchestration and infrastructure automation.**

Currently:

|Technology|Demonstrated in Projects?|
|---|--:|
|PySpark|✅|
|Neural Networks|✅|
|Computer Vision|✅|
|LLM / RAG|✅|
|FastAPI|✅|
|Docker|✅|
|MLflow|✅|
|Prometheus|✅|
|Grafana|✅|
|Kubernetes|⚠️ Mainly Skills|
|Kafka|❌|
|Airflow|❌|
|Terraform|❌|
|AWS|❌|

---

# 🏆 Recommended Final Portfolio

## 1. Connected Fleet Telemetry

### Distributed ML + Big Data + Streaming + Cloud + MLOps

**KEEP AND SIGNIFICANTLY EXPAND THIS PROJECT.**

This should become the **flagship data engineering / production ML project**.

Your existing project already has:

- 5 interconnected vehicle datasets
    
- 876,000 telemetry rows
    
- EDA
    
- PySpark
    
- Rolling 3h / 24h features
    
- Broadcast joins
    
- Spark MLlib
    
- Random Forest
    
- Chronological train/test split
    
- AUC-ROC = 0.97
    
- Failure recall = 89.6%
    

This is already a strong foundation.

---

## Target Architecture

```text
                    VEHICLE / SENSOR DATA
                            │
                            ▼
                         Kafka
                            │
                 ┌──────────┴──────────┐
                 │                     │
                 ▼                     ▼
             Raw Stream            AWS S3
                                       │
                                       ▼
                              Historical Storage
                                       │
                                       ▼
                                  PySpark
                                       │
                           ┌───────────┴───────────┐
                           │                       │
                           ▼                       ▼
                    Data Cleaning            Feature Engineering
                           │                       │
                           └───────────┬───────────┘
                                       ▼
                                  Spark ML
                                       │
                                       ▼
                              Failure Prediction
                                       │
                                       ▼
                                    MLflow
                                       │
                           ┌───────────┴───────────┐
                           │                       │
                           ▼                       ▼
                    Experiment Tracking       Model Registry
                                                   │
                                                   ▼
                                               FastAPI
                                                   │
                                                   ▼
                                               Docker
                                                   │
                                                   ▼
                                             Kubernetes
                                                   │
                                      ┌────────────┴────────────┐
                                      │                         │
                                      ▼                         ▼
                                 Prometheus                 Grafana
```

---

# Airflow Pipeline

Airflow should handle the **batch/retraining workflow**.

```text
                    Airflow DAG
                        │
                        ▼
                  Data Ingestion
                        │
                        ▼
                 Data Validation
                        │
                        ▼
                   PySpark ETL
                        │
                        ▼
                Feature Generation
                        │
                        ▼
                 Model Training
                        │
                        ▼
                     MLflow
                        │
                        ▼
                 Model Evaluation
                        │
                        ▼
                 Model Registration
                        │
                        ▼
                  Deployment
```

This makes Airflow actually useful rather than being added just because it is a popular technology.

---

# AWS Architecture

Use AWS where it makes architectural sense.

Potential structure:

```text
AWS
│
├── S3
│   ├── raw/
│   ├── processed/
│   └── features/
│
├── EC2 / ECS / EKS
│   └── Model Serving
│
├── CloudWatch
│   └── Infrastructure Logs
│
└── IAM
    └── Access Control
```

Depending on complexity, Kubernetes can eventually run on **EKS**.

---

# Terraform

Use Terraform to create the infrastructure rather than manually creating everything.

```text
Terraform
    │
    ├── S3
    ├── IAM
    ├── Compute
    ├── Networking
    └── Kubernetes / EKS
```

This demonstrates:

> **Infrastructure as Code**

instead of simply saying "I know AWS."

---

# MLOps Layer

```text
Code
 ↓
Git
 ↓
Docker
 ↓
MLflow
 ↓
Model Registry
 ↓
Kubernetes
 ↓
FastAPI
 ↓
Prometheus
 ↓
Grafana
```

---

# What Fleet Should Demonstrate

### Data Engineering

- Kafka
    
- AWS S3
    
- PySpark
    
- Distributed processing
    
- Data validation
    
- Feature engineering
    
- SQL
    

### Machine Learning

- Classification
    
- Feature engineering
    
- Time-based splitting
    
- Model evaluation
    
- Class imbalance
    
- Model comparison
    

### MLOps

- MLflow
    
- Model Registry
    
- Docker
    
- Kubernetes
    
- Airflow
    

### Cloud

- AWS
    
- S3
    
- IAM
    
- Compute
    
- EKS / container deployment
    

### Infrastructure

- Terraform
    

### Observability

- Prometheus
    
- Grafana
    

### Backend

- FastAPI
    

---

# 2. End-to-End Autonomous Steering

## Deep Learning + Computer Vision

**KEEP THIS PROJECT.**

This should represent your **Deep Learning / Computer Vision** expertise.

Your existing implementation already includes:

- NVIDIA-style CNN
    
- PyTorch
    
- Monocular road images
    
- Steering-angle prediction
    
- Cropping
    
- YUV conversion
    
- Gaussian blur
    
- Normalization
    
- Data augmentation
    
- Temporal smoothing
    
- Steering-vector visualization
    
- Validation MSE
    
- Autonomous driving simulation
    

This is a fundamentally different problem from Fleet.

---

# Target Architecture

```text
             ROAD IMAGES
                  │
                  ▼
             Dataset Loader
                  │
                  ▼
             Preprocessing
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
     Cropping           YUV Conversion
        │                   │
        └─────────┬─────────┘
                  ▼
              Augmentation
                  │
                  ▼
               CNN
                  │
                  ▼
          Steering Angle
                  │
                  ▼
          Temporal Smoothing
                  │
                  ▼
        Autonomous Simulation
```

---

# Improvements

Focus on making this a **really good deep learning project**, rather than adding every MLOps tool.

Potential improvements:

- Better CNN architecture experiments
    
- Hyperparameter tuning
    
- Learning-rate scheduling
    
- Model checkpointing
    
- TensorBoard / MLflow
    
- GPU training
    
- Reproducible training
    
- Train/validation/test methodology
    
- Error analysis
    
- Steering-angle distribution analysis
    
- FPS benchmarking
    
- Inference latency
    
- TorchScript / ONNX
    
- Dockerized inference
    

---

# Why Keep This?

Because none of the other projects demonstrate computer vision as strongly.

This gives the portfolio:

> **"I can build neural networks for real-world visual prediction problems."**

while Fleet demonstrates:

> **"I can build scalable ML systems around structured data."**

These are complementary rather than redundant.

---

# 3. AutoNotes-Pro

## LLM + RAG + NLP + AI Systems

**KEEP THIS AND EXPAND IT.**

Your current AutoNotes already demonstrates:

- Whisper
    
- Llama
    
- FastAPI
    
- ChromaDB
    
- Sentence Transformers
    
- Audio chunking
    
- Structured note generation
    
- Quiz generation
    
- Resource generation
    
- RAG
    
- Context-grounded Q&A
    
- On-device inference optimization
    

This should become your **Generative AI / LLM Systems project**.

---

# Target Architecture

```text
                    AUDIO
                      │
                      ▼
                   Whisper
                      │
                      ▼
                  Chunking
                      │
              ┌───────┴────────┐
              │                │
              ▼                ▼
        Summarization      Embeddings
              │                │
              ▼                ▼
            Notes          Vector DB
              │                │
              │                ▼
              │           Retrieval
              │                │
              │                ▼
              └────────────► LLM
                               │
                  ┌────────────┼────────────┐
                  │            │            │
                  ▼            ▼            ▼
                Notes        Q&A          Quiz
```

---

# RAG Pipeline

```text
Documents / Transcript
          │
          ▼
       Chunking
          │
          ▼
    Sentence Transformer
          │
          ▼
       Embeddings
          │
          ▼
       ChromaDB
          │
          ▼
       Retrieval
          │
          ▼
     Context + Query
          │
          ▼
          LLM
          │
          ▼
   Grounded Response
```

---

# Improvements

Rather than just saying:

> "I built a RAG application."

Make the project demonstrate that you understand **RAG engineering**.

Add:

### Retrieval Experiments

Compare:

- Different chunk sizes
    
- Different chunk overlap
    
- Different embedding models
    
- Top-k retrieval
    
- Reranking
    

### RAG Evaluation

Measure things such as:

- Retrieval relevance
    
- Context precision
    
- Context recall
    
- Answer faithfulness
    
- Answer relevance
    
- Hallucination rate
    

### LLM Evaluation

Compare:

```text
Model A
   vs
Model B

Latency
Accuracy
Faithfulness
Token usage
Memory usage
```

### Production

Add:

- FastAPI
    
- Docker
    
- AWS deployment
    
- Request logging
    
- Latency metrics
    
- Model/version tracking
    

---

# ❌ What To Do With CineScope

## Keep it on GitHub, but don't make it a flagship project.

CineScope is a good project.

It demonstrates:

- CNN
    
- LSTM
    
- NLP
    
- Hugging Face tokenizer
    
- FastAPI
    
- Docker Compose
    
- PostgreSQL
    
- Prometheus
    
- Grafana
    
- MLflow
    
- Model monitoring
    

But many of those technologies can be demonstrated more meaningfully in Fleet.

The biggest issue is that it makes your portfolio feel like:

```text
Project 1 → ML
Project 2 → CNN
Project 3 → LLM
Project 4 → CNN/LSTM + MLOps
```

Instead, you want:

```text
Project 1 → Production ML + Big Data
Project 2 → Deep Learning + Computer Vision
Project 3 → LLM + RAG
```

Much cleaner.

---

# 🧠 Portfolio Architecture

The three projects should represent three major ML domains.

```text
                     ML PORTFOLIO
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
     FLEET             STEERING          AUTONOTES
        │                 │                 │
        ▼                 ▼                 ▼
 Big Data / ML       Deep Learning       GenAI
        │                 │                 │
        ▼                 ▼                 ▼
   PySpark             PyTorch            LLM
   Kafka                CNN               RAG
   AWS                  CV                Embeddings
   Airflow                                  │
   MLflow                                   ▼
   Docker                               Vector DB
   K8s                                   FastAPI
   Terraform                             AWS
   Prometheus
   Grafana
```

---

# 📊 Overall Skill Coverage

|Skill|Fleet|Steering|AutoNotes|
|---|:-:|:-:|:-:|
|Python|✅|✅|✅|
|SQL|✅||✅|
|Classical ML|✅|||
|PySpark|✅|||
|Apache Spark|✅|||
|Big Data|✅|||
|Kafka|✅|||
|Airflow|✅|||
|AWS|✅||✅|
|S3|✅|||
|Terraform|✅|||
|Docker|✅|✅|✅|
|Kubernetes|✅|||
|MLflow|✅|✅||
|Prometheus|✅|||
|Grafana|✅|||
|FastAPI|✅||✅|
|Deep Learning||✅|✅|
|CNN||✅||
|Computer Vision||✅||
|NLP|||✅|
|LLM|||✅|
|RAG|||✅|
|Embeddings|||✅|
|Vector DB|||✅|

---

# 🏗️ The Bigger Picture

The portfolio should tell a story:

## Project 1 — Can I work with data at scale?

**Connected Fleet**

```text
Raw Data
 ↓
Streaming
 ↓
Cloud Storage
 ↓
Distributed Processing
 ↓
ML
 ↓
Deployment
 ↓
Monitoring
```

---

## Project 2 — Can I build deep learning models?

**Autonomous Steering**

```text
Raw Images
 ↓
Computer Vision Preprocessing
 ↓
Augmentation
 ↓
CNN
 ↓
Inference
 ↓
Real-world Simulation
```

---

## Project 3 — Can I build modern AI systems?

**AutoNotes-Pro**

```text
Audio
 ↓
Speech Recognition
 ↓
LLM
 ↓
Embeddings
 ↓
Vector Database
 ↓
RAG
 ↓
Grounded AI Application
```

---

# 🚀 Recommended Development Order

Don't try to build all three simultaneously.

## Phase 1 — Upgrade Fleet

Priority:

```text
1. Kafka
2. AWS S3
3. PySpark pipeline
4. Airflow
5. MLflow
6. Docker
7. FastAPI
8. Kubernetes
9. Prometheus
10. Grafana
11. Terraform
12. AWS deployment
```

This should become the **biggest and most technically impressive project**.

---

# Phase 2 — Upgrade AutoNotes

Priority:

```text
1. Better RAG pipeline
2. Retrieval experiments
3. RAG evaluation
4. Embedding comparison
5. Reranking
6. LLM evaluation
7. Production API
8. Docker
9. AWS deployment
10. Monitoring
```

The goal is to demonstrate:

> **LLM engineering rather than simply calling an LLM API.**

---

# Phase 3 — Polish Steering

Priority:

```text
1. Improve CNN experiments
2. Better augmentation
3. Hyperparameter experiments
4. Error analysis
5. GPU training
6. Model optimization
7. Inference benchmarking
8. Reproducibility
9. Optional Docker deployment
```

Don't overload it with unnecessary infrastructure.

---

# 🎯 Important Rule

## Don't add technologies just to increase the tech-stack count.

Bad:

```text
CNN
+ Kafka
+ Kubernetes
+ Terraform
+ Airflow
+ Spark
+ AWS
+ Redis
+ RabbitMQ
+ Jenkins
+ ArgoCD
```

if they don't serve the project.

Good:

```text
Fleet
→ Kafka because telemetry is streaming

Fleet
→ Spark because telemetry is large-scale

Fleet
→ Airflow because training/ETL needs orchestration

Fleet
→ AWS because data and infrastructure need cloud storage/compute

Fleet
→ Kubernetes because the prediction service needs scalable deployment

Fleet
→ Prometheus/Grafana because production inference needs observability

Fleet
→ Terraform because cloud infrastructure should be reproducible
```

Every technology should have a **reason for existing**.

---

# 💼 Resume Positioning

Eventually your Skills section can look something like:

```text
Machine Learning:
PyTorch, Scikit-Learn, Spark MLlib, TensorFlow

Big Data:
PySpark, Apache Spark, Apache Kafka

GenAI:
LLMs, RAG, LangChain, Sentence Transformers, ChromaDB

MLOps:
MLflow, Apache Airflow, Docker, Kubernetes

Cloud & Infrastructure:
AWS, Amazon S3, Terraform

Observability:
Prometheus, Grafana

Backend:
FastAPI, PostgreSQL

Programming:
Python, C++, SQL, Java
```

But **only list technologies that your projects actually demonstrate**.

---

# 🏆 Final Portfolio

### 🥇 Connected Fleet Telemetry

**Production ML / Big Data / Cloud / MLOps**

> Demonstrates that you can take large-scale telemetry from ingestion → distributed processing → ML → deployment → monitoring.

### 🥈 End-to-End Autonomous Steering

**Deep Learning / Computer Vision**

> Demonstrates that you can build and optimize neural networks for real-world visual prediction.

### 🥉 AutoNotes-Pro

**LLM / RAG / Generative AI**

> Demonstrates that you can build a complete AI application around speech recognition, embeddings, retrieval and LLMs.

### 📦 CineScope

**Secondary / GitHub Project**

> Keep it as evidence of additional NLP + MLOps experience, but don't spend valuable resume space on it if the three flagship projects are strong enough.

---

# 🎯 The Portfolio Story

The ideal recruiter takeaway should be:

> **"This person can work across the entire ML stack."**

From:

```text
                 DATA
                   ↓
          ┌─────────────────┐
          │ Big Data / SQL  │
          │ PySpark / Kafka │
          └────────┬────────┘
                   ↓
                 ML
                   ↓
       ┌───────────┼───────────┐
       ↓           ↓           ↓
   Classical     CNN          LLM
      ML          CV          RAG
       │           │           │
       └───────────┼───────────┘
                   ↓
              MLOps / MLflow
                   ↓
                Docker
                   ↓
              Kubernetes
                   ↓
                 AWS
                   ↓
              Monitoring
                   ↓
          Prometheus / Grafana
                   ↓
              Production
```

**That is a much stronger portfolio than having 4–5 smaller projects that each demonstrate a slightly different model.**

The main thing I'd focus on now is **turning Connected Fleet into the "monster" production ML project**. It already has the hardest part — a believable ML problem and a substantial dataset/pipeline — so the cloud, streaming, orchestration and MLOps layers can be added around an existing foundation rather than building another project from scratch.