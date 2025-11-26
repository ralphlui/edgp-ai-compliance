#!/bin/bash

# LangSmith Evaluation - Get Started Script
# Run this to set up and test LangSmith evaluation

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║      LangSmith Evaluation Setup for Compliance Agent              ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Check Python
echo "🐍 Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi
echo "✅ Python found: $(python3 --version)"
echo ""

# Check uv
echo "📦 Checking uv package manager..."
if ! command -v uv &> /dev/null; then
    echo "❌ uv not found. Please install: https://github.com/astral-sh/uv"
    exit 1
fi
echo "✅ uv found"
echo ""

# Function to retrieve API keys from AWS Secrets Manager
get_secret_key() {
    local secret_name=$1
    local key_name=$2
    
    # Get secret from AWS Secrets Manager
    local secret_value=$(aws secretsmanager get-secret-value \
        --secret-id "$secret_name" \
        --query SecretString \
        --output text \
        --region ap-southeast-1 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    # Extract the specific key using jq (or python if jq not available)
    if command -v jq &> /dev/null; then
        echo "$secret_value" | jq -r ".$key_name // empty"
    else
        echo "$secret_value" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('$key_name', ''))"
    fi
}

# Check environment variables and AWS Secrets Manager
echo "🔑 Checking API keys..."

# Get AWS secret name from environment or use default
AWS_SECRET_NAME="${AWS_SECRET_NAME:-dev/edgp/secret}"

# Check LANGCHAIN_API_KEY
if [ -z "$LANGCHAIN_API_KEY" ] || [ "$LANGCHAIN_API_KEY" = "placeholder_will_use_secrets_manager" ]; then
    echo "⚠️  LANGCHAIN_API_KEY not set in environment, retrieving from AWS Secrets Manager..."
    LANGCHAIN_API_KEY=$(get_secret_key "$AWS_SECRET_NAME" "langchain_api_key")
    
    if [ -z "$LANGCHAIN_API_KEY" ]; then
        # Try alternate key name
        LANGCHAIN_API_KEY=$(get_secret_key "$AWS_SECRET_NAME" "LANGCHAIN_API_KEY")
    fi
    
    if [ -z "$LANGCHAIN_API_KEY" ]; then
        echo "❌ LANGCHAIN_API_KEY not found in AWS Secrets Manager ($AWS_SECRET_NAME)"
        echo "   Please add 'langchain_api_key' to the secret with value: lsv2_pt_your_key_here"
        exit 1
    fi
    
    export LANGCHAIN_API_KEY
    echo "✅ LANGCHAIN_API_KEY retrieved from AWS Secrets Manager"
else
    echo "✅ LANGCHAIN_API_KEY found in environment"
fi
echo ""

# Check OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "placeholder_will_use_secrets_manager" ]; then
    echo "⚠️  OPENAI_API_KEY not set in environment, retrieving from AWS Secrets Manager..."
    OPENAI_API_KEY=$(get_secret_key "$AWS_SECRET_NAME" "openai_api_key")
    
    if [ -z "$OPENAI_API_KEY" ]; then
        # Try alternate key names
        OPENAI_API_KEY=$(get_secret_key "$AWS_SECRET_NAME" "ai_agent_api_key")
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        OPENAI_API_KEY=$(get_secret_key "$AWS_SECRET_NAME" "OPENAI_API_KEY")
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "❌ OPENAI_API_KEY not found in AWS Secrets Manager ($AWS_SECRET_NAME)"
        echo "   Please add 'openai_api_key' or 'ai_agent_api_key' to the secret"
        exit 1
    fi
    
    export OPENAI_API_KEY
    echo "✅ OPENAI_API_KEY retrieved from AWS Secrets Manager"
else
    echo "✅ OPENAI_API_KEY found in environment"
fi
echo ""

# Install dependencies
echo "📥 Installing LangSmith dependencies..."
uv pip install langsmith langchain-benchmarks numpy
echo "✅ Dependencies installed"
echo ""

# Step 1: Create Dataset
echo "════════════════════════════════════════════════════════════════════"
echo "STEP 1: Creating LangSmith Dataset"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "This will create a test dataset with 6 compliance violation examples."
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."
echo ""

uv run python scripts/create_langsmith_dataset.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Dataset creation failed. Please check the error above."
    exit 1
fi

# Get dataset name (from today's date)
DATASET_NAME="compliance-violations-test-$(date +%Y%m%d)"
echo ""
echo "✅ Dataset created: $DATASET_NAME"
echo ""

# Step 2: Run Baseline Experiment
echo "════════════════════════════════════════════════════════════════════"
echo "STEP 2: Running Baseline Experiment"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "This will test your current compliance agent configuration."
echo "Estimated time: 2-3 minutes"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."
echo ""

uv run python scripts/run_langsmith_experiment.py \
    --dataset "$DATASET_NAME" \
    --mode baseline

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Experiment failed. Please check the error above."
    exit 1
fi

echo ""
echo "✅ Baseline experiment completed!"
echo ""

# Step 3: View Results
echo "════════════════════════════════════════════════════════════════════"
echo "STEP 3: View Results"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "🎉 Setup complete! Here's what you can do next:"
echo ""
echo "1. VIEW RESULTS IN UI"
echo "   → https://smith.langchain.com/o/edgp-ai-compliance"
echo ""
echo "2. RUN COMPARISON EXPERIMENTS"
echo "   → uv run python scripts/run_langsmith_experiment.py \\"
echo "       --dataset \"$DATASET_NAME\" \\"
echo "       --mode compare"
echo ""
echo "3. TEST CUSTOM CONFIGURATION"
echo "   → uv run python scripts/run_langsmith_experiment.py \\"
echo "       --dataset \"$DATASET_NAME\" \\"
echo "       --mode custom \\"
echo "       --name \"my-test\" \\"
echo "       --model \"gpt-4\" \\"
echo "       --temperature 0.1"
echo ""
echo "4. USE ALL EVALUATORS (including LLM judge)"
echo "   → uv run python scripts/run_langsmith_experiment.py \\"
echo "       --dataset \"$DATASET_NAME\" \\"
echo "       --mode baseline \\"
echo "       --all-evaluators"
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "📚 DOCUMENTATION"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "• Quick Start Guide:"
echo "  → LANGSMITH_QUICK_START.md"
echo ""
echo "• Full Documentation:"
echo "  → LANGSMITH_EVALUATION_GUIDE.md"
echo ""
echo "• Setup Summary:"
echo "  → LANGSMITH_SETUP_SUMMARY.md"
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ LangSmith evaluation is ready to use!"
echo ""
