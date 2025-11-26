"""
Capture Production Traces to LangSmith Dataset

This script retrieves traces from your running compliance agent
(project: edgp-ai-compliance) and converts them into a dataset for evaluation.
"""

from langsmith import Client
from datetime import datetime, timedelta
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compliance_agent.utils.logger import get_logger

logger = get_logger(__name__)


def extract_input_from_trace(trace) -> dict:
    """
    Extract input parameters from trace metadata or inputs
    
    Expected format from your compliance agent prompt:
    - Customer ID: 15
    - Violation Type: DATA_RETENTION_EXCEEDED
    - Data Age: 9158 days
    - Retention Limit: 2555 days
    - Excess Period: 6603 days
    - Framework: PDPA
    """
    try:
        # Try to get inputs from the trace
        if hasattr(trace, 'inputs') and trace.inputs:
            inputs = trace.inputs
            
            # If inputs is a dict with prompt text, parse it
            if isinstance(inputs, dict):
                prompt_text = inputs.get('input', '') or inputs.get('prompt', '') or str(inputs)
                
                # For ChatOpenAI traces, extract from messages
                if 'messages' in inputs:
                    messages = inputs['messages']
                    if isinstance(messages, list) and len(messages) > 0:
                        # Look through messages for HumanMessage with compliance content
                        for msg_list in messages:
                            if isinstance(msg_list, list):
                                for msg in msg_list:
                                    if isinstance(msg, dict) and msg.get('kwargs', {}).get('content'):
                                        content = msg['kwargs']['content']
                                        if 'Customer ID:' in content:
                                            prompt_text = content
                                            break
                
                # Parse the prompt to extract structured data
                parsed = {}
                
                # Extract Customer ID
                if 'Customer ID:' in prompt_text:
                    try:
                        customer_id = prompt_text.split('Customer ID:')[1].split('\n')[0].strip()
                        parsed['customer_id'] = customer_id
                    except:
                        pass
                
                # Extract Data Age
                if 'Data Age:' in prompt_text:
                    try:
                        data_age = prompt_text.split('Data Age:')[1].split('days')[0].strip()
                        parsed['data_age_days'] = int(data_age)
                    except:
                        pass
                
                # Extract Retention Limit
                if 'Retention Limit:' in prompt_text:
                    try:
                        retention_limit = prompt_text.split('Retention Limit:')[1].split('days')[0].strip()
                        parsed['retention_limit_days'] = int(retention_limit)
                    except:
                        pass
                
                # Extract Excess Period
                if 'Excess Period:' in prompt_text:
                    try:
                        excess = prompt_text.split('Excess Period:')[1].split('days')[0].strip()
                        parsed['excess_days'] = int(excess)
                    except:
                        pass
                
                # Extract Framework
                if 'Framework:' in prompt_text:
                    try:
                        framework = prompt_text.split('Framework:')[1].split('\n')[0].strip()
                        parsed['framework'] = framework
                    except:
                        pass
                
                # Determine region based on framework
                if 'framework' in parsed:
                    parsed['region'] = 'Singapore' if parsed['framework'] == 'PDPA' else 'European Union'
                
                if parsed:
                    return parsed
        
        # Fallback: try metadata
        if hasattr(trace, 'extra') and trace.extra:
            metadata = trace.extra.get('metadata', {})
            if metadata:
                return metadata
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract inputs from trace: {e}")
        return None


def extract_output_from_trace(trace) -> dict:
    """
    Extract output from trace
    
    Expected format:
    {
        "description": "...",
        "recommendation": "...",
        "legal_reference": "...",
        "urgency_level": "HIGH/MEDIUM/LOW",
        "compliance_impact": "..."
    }
    """
    try:
        if hasattr(trace, 'outputs') and trace.outputs:
            output = trace.outputs
            
            # If output is already a dict with the right structure
            if isinstance(output, dict):
                # Check if it has the expected keys
                if all(key in output for key in ['description', 'recommendation', 'legal_reference', 'urgency_level']):
                    return output
                
                # Try to extract from nested structures
                if 'output' in output:
                    return extract_output_from_trace_helper(output['output'])
                
                # LangChain ChatOpenAI returns generations structure
                if 'generations' in output:
                    generations = output['generations']
                    if isinstance(generations, list) and len(generations) > 0:
                        first_gen = generations[0]
                        if isinstance(first_gen, list) and len(first_gen) > 0:
                            message = first_gen[0].get('message', {})
                            if isinstance(message, dict):
                                kwargs = message.get('kwargs', {})
                                content = kwargs.get('content', '')
                                if content:
                                    try:
                                        parsed = json.loads(content)
                                        if isinstance(parsed, dict) and 'description' in parsed:
                                            return parsed
                                    except:
                                        pass
                
                # LangChain ChatOpenAI returns AIMessage with content
                if 'content' in output:
                    content = output['content']
                    try:
                        parsed = json.loads(content) if isinstance(content, str) else content
                        if isinstance(parsed, dict) and 'description' in parsed:
                            return parsed
                    except:
                        pass
                
                # Try to parse any string value as JSON
                for key in output:
                    if isinstance(output[key], str):
                        try:
                            parsed = json.loads(output[key])
                            if isinstance(parsed, dict) and 'description' in parsed:
                                return parsed
                        except:
                            pass
            
            # If output is a string, try to parse it
            if isinstance(output, str):
                try:
                    parsed = json.loads(output)
                    if isinstance(parsed, dict) and 'description' in parsed:
                        return parsed
                except:
                    pass
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract output from trace: {e}")
        return None


def extract_output_from_trace_helper(output):
    """Helper to recursively extract output"""
    if isinstance(output, dict):
        if all(key in output for key in ['description', 'recommendation', 'legal_reference']):
            return output
        for value in output.values():
            result = extract_output_from_trace_helper(value)
            if result:
                return result
    elif isinstance(output, str):
        try:
            parsed = json.loads(output)
            return extract_output_from_trace_helper(parsed)
        except:
            pass
    return None


def capture_traces_to_dataset(
    project_name: str = "edgp-ai-compliance",
    hours_back: int = 24,
    min_examples: int = 5,
    max_examples: int = 50,
    dataset_name_suffix: str = "production"
):
    """
    Capture traces from production and create a dataset
    
    Args:
        project_name: LangSmith project name (your running app)
        hours_back: How many hours back to look for traces
        min_examples: Minimum examples needed to create dataset
        max_examples: Maximum examples to include
        dataset_name_suffix: Suffix for dataset name
    """
    client = Client()
    
    logger.info(f"🔍 Searching for traces in project: {project_name}")
    logger.info(f"📅 Looking back: {hours_back} hours")
    
    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours_back)
    
    # Get traces from the project (both root and child runs)
    try:
        all_traces = client.list_runs(
            project_name=project_name,
            start_time=start_time,
            end_time=end_time
        )
        
        logger.info("✅ Connected to LangSmith")
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch traces: {e}")
        return None
    
    # Process traces into examples
    examples = []
    processed_count = 0
    
    for trace in all_traces:
        if len(examples) >= max_examples:
            break
        
        processed_count += 1
        
        # Extract inputs and outputs
        inputs = extract_input_from_trace(trace)
        outputs = extract_output_from_trace(trace)
        
        if inputs and outputs:
            example = {
                "inputs": inputs,
                "outputs": outputs,
                "metadata": {
                    "trace_id": str(trace.id),
                    "captured_at": trace.start_time.isoformat() if hasattr(trace, 'start_time') else None,
                    "source": "production_trace",
                    "trace_name": trace.name if hasattr(trace, 'name') else None
                }
            }
            examples.append(example)
            logger.info(f"  ✅ Captured example {len(examples)}: Customer {inputs.get('customer_id', 'N/A')}")
        else:
            if inputs and not outputs:
                logger.debug(f"  ⚠️  Trace {trace.id} ({trace.name}): No valid outputs found")
            elif outputs and not inputs:
                logger.debug(f"  ⚠️  Trace {trace.id} ({trace.name}): No valid inputs found")
    
    logger.info(f"\n📊 Processed {processed_count} traces")
    logger.info(f"✅ Captured {len(examples)} valid examples")
    
    # Check if we have enough examples
    if len(examples) < min_examples:
        logger.error(f"❌ Not enough examples captured: {len(examples)} < {min_examples}")
        logger.error("   💡 Try increasing hours_back or running your compliance agent first")
        return None
    
    # Create dataset
    dataset_name = f"compliance-violations-{dataset_name_suffix}-{datetime.now().strftime('%Y%m%d-%H%M')}"
    description = f"Dataset captured from production traces ({project_name}) - {len(examples)} examples"
    
    try:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=description
        )
        logger.info(f"\n✅ Created dataset: {dataset.name} (ID: {dataset.id})")
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info(f"📊 Dataset '{dataset_name}' already exists, retrieving it...")
            datasets = client.list_datasets(dataset_name=dataset_name)
            dataset = next((d for d in datasets if d.name == dataset_name), None)
            if dataset:
                logger.info(f"✅ Using existing dataset: {dataset.name}")
            else:
                logger.error("❌ Could not retrieve existing dataset")
                return None
        else:
            logger.error(f"❌ Failed to create dataset: {e}")
            return None
    
    # Add examples to dataset
    added_count = 0
    for example in examples:
        try:
            client.create_example(
                dataset_id=dataset.id,
                inputs=example["inputs"],
                outputs=example["outputs"],
                metadata=example.get("metadata", {})
            )
            added_count += 1
        except Exception as e:
            logger.error(f"  ❌ Failed to add example: {e}")
    
    logger.info(f"\n🎉 Dataset created successfully!")
    logger.info(f"📊 Dataset Name: {dataset_name}")
    logger.info(f"📊 Dataset ID: {dataset.id}")
    logger.info(f"📊 Examples Added: {added_count}/{len(examples)}")
    logger.info(f"🔗 View dataset: https://smith.langchain.com/o/datasets/{dataset.id}")
    
    return dataset


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Capture production traces to LangSmith dataset")
    parser.add_argument("--project", default="edgp-ai-compliance", help="LangSmith project name")
    parser.add_argument("--hours", type=int, default=24, help="Hours back to search for traces")
    parser.add_argument("--min-examples", type=int, default=5, help="Minimum examples needed")
    parser.add_argument("--max-examples", type=int, default=50, help="Maximum examples to capture")
    parser.add_argument("--suffix", default="production", help="Dataset name suffix")
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("CAPTURE PRODUCTION TRACES TO DATASET")
    print("="*80 + "\n")
    
    # Check environment variables
    if not os.getenv("LANGCHAIN_API_KEY"):
        print("❌ ERROR: LANGCHAIN_API_KEY not set")
        print("Please set it in your environment or run with setup_langsmith.sh")
        exit(1)
    
    dataset = capture_traces_to_dataset(
        project_name=args.project,
        hours_back=args.hours,
        min_examples=args.min_examples,
        max_examples=args.max_examples,
        dataset_name_suffix=args.suffix
    )
    
    if dataset:
        print("\n✅ SUCCESS: Dataset created from production traces")
        print(f"📊 Use this dataset name in experiments: {dataset.name}")
        print(f"\n💡 Next steps:")
        print(f"   1. Run baseline experiment:")
        print(f"      uv run python scripts/run_langsmith_experiment.py \\")
        print(f"        --dataset \"{dataset.name}\" \\")
        print(f"        --mode baseline")
        print(f"\n   2. View dataset in UI:")
        print(f"      https://smith.langchain.com")
    else:
        print("\n❌ FAILED: Could not create dataset from traces")
        print("   💡 Make sure your compliance agent is running and processing violations")
        exit(1)
