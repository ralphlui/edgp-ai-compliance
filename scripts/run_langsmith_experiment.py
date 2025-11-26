"""
Run LangSmith Experiments

Test compliance agent with different configurations.
"""

from langsmith import Client
from langsmith.evaluation import aevaluate
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.langsmith_evaluators import FAST_EVALUATORS, ALL_EVALUATORS
from src.compliance_agent.utils.logger import get_logger

logger = get_logger(__name__)


def create_compliance_prompt(inputs: dict) -> str:
    """
    Generate compliance analysis prompt from inputs
    """
    return f"""
You are an international data compliance expert specializing in {inputs['framework']}.

VIOLATION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Data Age: {inputs['data_age_days']} days
⏰ Retention Limit: {inputs['retention_limit_days']} days
⚠️  Excess Days: {inputs['excess_days']} days
🌍 Framework: {inputs['framework']}
📍 Region: {inputs['region']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK: Provide a detailed compliance analysis including:
1. 📝 DESCRIPTION - Explain WHY this is a violation (mention excess days)
2. 🔧 RECOMMENDATION - Specify CONCRETE actions to remediate
3. 📚 LEGAL REFERENCE - Cite specific article/section (e.g., PDPA Article 25, GDPR Article 17)
4. ⚡ URGENCY LEVEL - Classify as HIGH (>5000 days), MEDIUM (1000-5000), or LOW (<1000)
5. ⚠️  COMPLIANCE IMPACT - Describe potential regulatory consequences

FORMAT: Return ONLY a JSON object with keys:
{{"description": "<string>", "recommendation": "<string>", "legal_reference": "<string>", "urgency_level": "<HIGH|MEDIUM|LOW>", "compliance_impact": "<string>"}}

IMPORTANT: Return ONLY the JSON object, no preamble or markdown.
"""


async def run_experiment(
    dataset_name: str,
    experiment_name: str,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.1,
    max_tokens: int = 500,
    use_all_evaluators: bool = False
):
    """
    Run an experiment against a dataset with evaluators
    
    Args:
        dataset_name: Name of LangSmith dataset
        experiment_name: Name for this experiment
        model: OpenAI model to use
        temperature: LLM temperature (0.0-1.0)
        max_tokens: Maximum tokens for response
        use_all_evaluators: If True, includes LLM-judge (slower but higher quality)
    """
    logger.info(f"🧪 Starting experiment: {experiment_name}")
    logger.info(f"📊 Dataset: {dataset_name}")
    logger.info(f"🤖 Model: {model}")
    logger.info(f"🌡️  Temperature: {temperature}")
    
    client = Client()
    
    # Initialize LLM
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    # Choose evaluators
    evaluators = ALL_EVALUATORS if use_all_evaluators else FAST_EVALUATORS
    logger.info(f"📈 Using {len(evaluators)} evaluators")
    
    # Define prediction function
    async def predict(inputs: dict) -> dict:
        """Make prediction for a single example"""
        try:
            prompt = create_compliance_prompt(inputs)
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            
            # Parse JSON response
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse LLM response: {e}")
            logger.error(f"Response: {response.content[:200]}")
            return {
                "description": "Error: Invalid JSON response",
                "recommendation": "Error",
                "legal_reference": "Error",
                "urgency_level": "UNKNOWN",
                "compliance_impact": "Error"
            }
        except Exception as e:
            logger.error(f"❌ Prediction failed: {e}")
            return {
                "description": f"Error: {str(e)}",
                "recommendation": "Error",
                "legal_reference": "Error",
                "urgency_level": "UNKNOWN",
                "compliance_impact": "Error"
            }
    
    # Run evaluation
    try:
        results = await aevaluate(
            predict,
            data=dataset_name,
            evaluators=evaluators,
            experiment_prefix=experiment_name,
            max_concurrency=2,  # Run 2 examples in parallel
            metadata={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "prompt_version": "v2.0"
            }
        )
        
        logger.info(f"\n✅ Experiment completed: {experiment_name}")
        logger.info(f"📊 Results summary:")
        
        # AsyncExperimentResults has aggregate_metrics property
        if hasattr(results, 'aggregate_metrics') and results.aggregate_metrics:
            for key, value in results.aggregate_metrics.items():
                if isinstance(value, (int, float)):
                    logger.info(f"  {key}: {value:.3f}")
        
        # Also show experiment URL if available
        if hasattr(results, 'experiment_url'):
            logger.info(f"\n🔗 View results: {results.experiment_url}")
        
        return results
    
    except Exception as e:
        logger.error(f"❌ Experiment failed: {e}")
        raise


async def run_baseline_experiment(dataset_name: str):
    """Run baseline experiment with current production config"""
    return await run_experiment(
        dataset_name=dataset_name,
        experiment_name="baseline-gpt35-temp01",
        model="gpt-3.5-turbo",
        temperature=0.1,
        max_tokens=500,
        use_all_evaluators=False
    )


async def run_comparison_experiments(dataset_name: str):
    """Run multiple experiments to compare configurations"""
    
    experiments = [
        # Baseline
        {
            "name": "exp1-baseline-gpt35-temp01",
            "model": "gpt-3.5-turbo",
            "temperature": 0.1,
            "description": "Current production config"
        },
        # Higher temperature
        {
            "name": "exp2-gpt35-temp03",
            "model": "gpt-3.5-turbo",
            "temperature": 0.3,
            "description": "More creative responses"
        },
        # Lower temperature
        {
            "name": "exp3-gpt35-temp00",
            "model": "gpt-3.5-turbo",
            "temperature": 0.0,
            "description": "Fully deterministic"
        },
    ]
    
    results = {}
    
    for exp in experiments:
        logger.info(f"\n{'='*80}")
        logger.info(f"Running: {exp['description']}")
        logger.info(f"{'='*80}\n")
        
        try:
            result = await run_experiment(
                dataset_name=dataset_name,
                experiment_name=exp["name"],
                model=exp["model"],
                temperature=exp["temperature"],
                use_all_evaluators=False
            )
            results[exp["name"]] = result
        except Exception as e:
            logger.error(f"❌ Experiment {exp['name']} failed: {e}")
            results[exp["name"]] = None
    
    # Print comparison
    logger.info(f"\n{'='*80}")
    logger.info("EXPERIMENT COMPARISON")
    logger.info(f"{'='*80}\n")
    
    for exp_name, result in results.items():
        if result:
            logger.info(f"\n{exp_name}:")
            for key, value in result.items():
                if isinstance(value, (int, float)):
                    logger.info(f"  {key}: {value:.3f}")
        else:
            logger.info(f"\n{exp_name}: FAILED")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LangSmith experiments")
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Name of the LangSmith dataset"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["baseline", "compare", "custom"],
        default="baseline",
        help="Experiment mode"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-3.5-turbo",
        help="OpenAI model (for custom mode)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature (for custom mode)"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="custom-experiment",
        help="Experiment name (for custom mode)"
    )
    parser.add_argument(
        "--all-evaluators",
        action="store_true",
        help="Use all evaluators including LLM-judge (slower)"
    )
    
    args = parser.parse_args()
    
    # Check environment
    if not os.getenv("LANGCHAIN_API_KEY"):
        print("❌ ERROR: LANGCHAIN_API_KEY not set")
        exit(1)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ ERROR: OPENAI_API_KEY not set")
        exit(1)
    
    # Run experiments
    print("\n" + "="*80)
    print("LANGSMITH EXPERIMENT RUNNER")
    print("="*80 + "\n")
    
    if args.mode == "baseline":
        asyncio.run(run_baseline_experiment(args.dataset))
    
    elif args.mode == "compare":
        asyncio.run(run_comparison_experiments(args.dataset))
    
    elif args.mode == "custom":
        asyncio.run(run_experiment(
            dataset_name=args.dataset,
            experiment_name=args.name,
            model=args.model,
            temperature=args.temperature,
            use_all_evaluators=args.all_evaluators
        ))
    
    print("\n✅ Experiments completed")
    print("🔗 View results: https://smith.langchain.com")
