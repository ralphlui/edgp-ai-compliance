# AI Compliance Agent

An intelligent AI-powered compliance checking system for PDPA (Singapore), international data privacy regulations (GDPR, CCPA), and data governance. This system is specifically designed for Master Data Governance web applications hosted in Singapore.

## 🚀 Features

- **Multi-Framework Compliance**: Support for PDPA Singapore, GDPR EU, CCPA California, and more
- **AI-Powered Analysis**: Advanced ML/NLP analysis beyond rule-based checking
- **Privacy Impact Assessments**: Automated DPIA/PIA generation and analysis
- **Data Breach Management**: Incident reporting and notification workflow
- **Consent Management**: Track and manage data subject consent
- **Real-time API**: RESTful API with comprehensive endpoints
- **Singapore-Focused**: Specialized support for Singapore's regulatory environment

## 🏗️ Architecture

```
├── src/compliance_agent/           # Main application code
│   ├── core/                      # Core compliance engine
│   ├── models/                    # Data models and schemas
│   ├── services/                  # Business logic services
│   ├── api/                       # FastAPI endpoints
│   └── utils/                     # Utilities and helpers
├── tests/                         # Comprehensive test suite
│   ├── unit/                      # Unit tests
│   └── integration/               # Integration tests
├── config/                        # Configuration management
└── docs/                          # Documentation
```

## 🛠️ Technology Stack

- **Framework**: FastAPI (high-performance async API)
- **AI/ML**: OpenAI GPT, LangChain, scikit-learn, transformers
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis for performance optimization
- **Testing**: pytest with comprehensive coverage
- **Deployment**: Docker & Docker Compose
- **Documentation**: MkDocs with Material theme

## 📋 Prerequisites

- Python 3.8 or higher
- PostgreSQL 12+
- Redis 6+
- Docker (optional)
- OpenAI API key (for AI features)

## 🚀 Quick Start

### Option 1: Automatic Setup

```bash
# Clone the repository
git clone <repository-url>
cd 0001_ai_Compliance_agent

# Run setup script (creates venv, installs dependencies, runs tests)
chmod +x setup.sh
./setup.sh

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Start the application
source venv/bin/activate
python main.py
```

### Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run tests
pytest tests/ -v

# Start application
python main.py
```

### Option 3: Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f compliance-agent
```

## 🔧 Configuration

Key configuration options in `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/compliance_db

# AI Settings
OPENAI_API_KEY=your_openai_api_key
AI_MODEL_NAME=gpt-3.5-turbo

# Singapore PDPA Settings
PDPC_NOTIFICATION_THRESHOLD=500
PDPC_NOTIFICATION_TIMEFRAME_HOURS=72

# Security
SECRET_KEY=your-secret-key-here
```

## 📚 API Documentation

Once running, access interactive API documentation at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

#### Compliance Checking

```bash
POST /api/v1/compliance/check
```

Assess data processing activities against compliance frameworks.

#### Privacy Impact Assessment

```bash
POST /api/v1/privacy/pia
```

Conduct automated Privacy Impact Assessments.

#### Data Breach Reporting

```bash
POST /api/v1/governance/breach/report
```

Report and manage data breach incidents.

#### Consent Management

```bash
POST /api/v1/privacy/consent
GET /api/v1/privacy/consent/{subject_id}
DELETE /api/v1/privacy/consent/{consent_id}
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## 🎯 Usage Examples

### 1. Compliance Assessment

```python
import requests

# Define data processing activity
activity = {
    "id": "customer_registration",
    "name": "Customer Registration Process",
    "purpose": "Collect customer information for account creation",
    "data_types": ["personal_data", "financial_data"],
    "legal_bases": ["consent", "contract"],
    "recipients": ["internal_team", "payment_processor"],
    "cross_border_transfers": False,
    "automated_decision_making": False
}

# Check compliance
response = requests.post("http://localhost:8000/api/v1/compliance/check", json={
    "activity": activity,
    "frameworks": ["pdpa_singapore", "gdpr_eu"],
    "include_ai_analysis": True
})

result = response.json()
print(f"Overall Status: {result['overall_status']}")
print(f"Compliance Score: {result['summary']['average_score']}")
```

### 2. Privacy Impact Assessment

```python
# Conduct PIA
pia_response = requests.post("http://localhost:8000/api/v1/privacy/pia", json={
    "project_name": "Customer Portal Upgrade",
    "description": "Upgrading customer portal with new features",
    "processing_activities": [activity]
})

pia = pia_response.json()["assessment"]
print(f"Overall Risk: {pia['overall_risk']}")
print(f"DPA Consultation Required: {pia['requires_consultation']}")
```

## 🏢 Singapore PDPA Compliance

This system provides specialized support for Singapore's Personal Data Protection Act:

- **Consent Management**: Granular consent tracking and withdrawal
- **Notification Requirements**: Automated PDPC notification workflows
- **Data Protection Obligations**: Comprehensive security assessment
- **Cross-border Transfers**: Transfer impact assessment
- **Individual Rights**: Data subject access request handling

## 🌏 International Compliance

Supports major international privacy frameworks:

- **GDPR (EU)**: Full Article 35 DPIA support, lawful basis validation
- **CCPA (California)**: Consumer rights and disclosure requirements
- **PIPEDA (Canada)**: Privacy breach notification
- **LGPD (Brazil)**: Data protection principles
- **ISO 27001**: Information security management
