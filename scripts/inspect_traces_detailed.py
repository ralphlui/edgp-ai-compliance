"""
Detailed inspection of LangSmith traces including child runs
"""

from langsmith import Client
from datetime import datetime, timedelta
import os
import json

# Get API key from AWS
import subprocess

result = subprocess.run([
    'aws', 'secretsmanager', 'get-secret-value',
    '--secret-id', 'dev/edgp/secret',
    '--query', 'SecretString',
    '--output', 'text',
    '--region', 'ap-southeast-1'
], capture_output=True, text=True)

if result.returncode == 0:
    secret = json.loads(result.stdout)
    os.environ['LANGCHAIN_API_KEY'] = secret.get('langchain_api_key', secret.get('LANGCHAIN_API_KEY', ''))

client = Client()

print("\n" + "="*80)
print("DETAILED TRACE INSPECTION - INCLUDING CHILD RUNS")
print("="*80 + "\n")

# Check traces in the last 7 days
end_time = datetime.now()
start_time = end_time - timedelta(days=7)

print(f"📅 Searching from {start_time} to {end_time}")
print(f"🔍 Project: edgp-ai-compliance\n")

try:
    # Get ALL runs (including children)
    all_runs = list(client.list_runs(
        project_name="edgp-ai-compliance",
        start_time=start_time,
        end_time=end_time
    ))
    
    print(f"Total runs found: {len(all_runs)}\n")
    
    # Group by parent
    root_runs = [r for r in all_runs if not r.parent_run_id]
    child_runs = [r for r in all_runs if r.parent_run_id]
    
    print(f"Root runs: {len(root_runs)}")
    print(f"Child runs: {len(child_runs)}\n")
    
    # Show first few child runs (these are the LLM calls)
    print("="*80)
    print("CHILD RUNS (LLM Calls)")
    print("="*80)
    
    for i, run in enumerate(child_runs[:5]):
        print(f"\n--- Child Run #{i+1} ---")
        print(f"ID: {run.id}")
        print(f"Name: {run.name}")
        print(f"Parent ID: {run.parent_run_id}")
        print(f"Run Type: {run.run_type if hasattr(run, 'run_type') else 'N/A'}")
        
        print(f"\n📥 INPUTS:")
        if hasattr(run, 'inputs') and run.inputs:
            input_str = json.dumps(run.inputs, indent=2)
            # Show first 500 chars
            print(input_str[:1000])
            if len(input_str) > 1000:
                print(f"... ({len(input_str)} chars total)")
        else:
            print("  (no inputs)")
        
        print(f"\n📤 OUTPUTS:")
        if hasattr(run, 'outputs') and run.outputs:
            output_str = json.dumps(run.outputs, indent=2)
            print(output_str[:1000])
            if len(output_str) > 1000:
                print(f"... ({len(output_str)} chars total)")
        else:
            print("  (no outputs)")
        
        print("\n" + "="*80)
    
    # Look for runs with "compliance" in the name or containing the prompt
    print("\nSEARCHING FOR COMPLIANCE-RELATED RUNS...")
    compliance_runs = []
    
    for run in all_runs:
        # Check name
        if hasattr(run, 'name') and ('compliance' in run.name.lower() or 'chat' in run.name.lower() or 'openai' in run.name.lower()):
            compliance_runs.append(run)
            continue
        
        # Check if inputs contain the compliance prompt
        if hasattr(run, 'inputs') and run.inputs:
            input_str = str(run.inputs)
            if 'compliance expert' in input_str.lower() or 'violation details' in input_str.lower():
                compliance_runs.append(run)
    
    print(f"\nFound {len(compliance_runs)} compliance-related runs")
    
    if compliance_runs:
        print("\n" + "="*80)
        print("COMPLIANCE-RELATED RUNS")
        print("="*80)
        
        for i, run in enumerate(compliance_runs[:3]):
            print(f"\n--- Compliance Run #{i+1} ---")
            print(f"ID: {run.id}")
            print(f"Name: {run.name}")
            print(f"Run Type: {run.run_type if hasattr(run, 'run_type') else 'N/A'}")
            print(f"Is Root: {not run.parent_run_id}")
            
            print(f"\n📥 INPUTS (first 1500 chars):")
            if hasattr(run, 'inputs') and run.inputs:
                print(json.dumps(run.inputs, indent=2)[:1500])
            
            print(f"\n📤 OUTPUTS (first 1500 chars):")
            if hasattr(run, 'outputs') and run.outputs:
                print(json.dumps(run.outputs, indent=2)[:1500])
            
            print("\n" + "="*80)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
