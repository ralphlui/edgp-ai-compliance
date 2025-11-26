"""
Quick script to check what traces exist in LangSmith project
"""

from langsmith import Client
from datetime import datetime, timedelta
import os

# Get API key from AWS
import subprocess
import json

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
print("CHECKING LANGSMITH PROJECT FOR TRACES")
print("="*80 + "\n")

# Check traces in the last 7 days
end_time = datetime.now()
start_time = end_time - timedelta(days=7)

print(f"📅 Searching from {start_time} to {end_time}")
print(f"🔍 Project: edgp-ai-compliance\n")

try:
    traces = client.list_runs(
        project_name="edgp-ai-compliance",
        start_time=start_time,
        end_time=end_time,
        is_root=True
    )
    
    count = 0
    for trace in traces:
        count += 1
        print(f"\n{'='*80}")
        print(f"Trace #{count}")
        print(f"{'='*80}")
        print(f"ID: {trace.id}")
        print(f"Name: {trace.name}")
        print(f"Start: {trace.start_time}")
        print(f"Status: {trace.status if hasattr(trace, 'status') else 'N/A'}")
        
        print(f"\n📥 INPUTS:")
        if hasattr(trace, 'inputs') and trace.inputs:
            print(json.dumps(trace.inputs, indent=2)[:1000])
        else:
            print("  (no inputs)")
        
        print(f"\n📤 OUTPUTS:")
        if hasattr(trace, 'outputs') and trace.outputs:
            print(json.dumps(trace.outputs, indent=2)[:1000])
        else:
            print("  (no outputs)")
        
        if count >= 3:  # Show first 3 traces
            break
    
    print(f"\n{'='*80}")
    print(f"Total traces found: {count}")
    print(f"{'='*80}\n")
    
    if count == 0:
        print("⚠️  No traces found!")
        print("\n💡 To generate traces:")
        print("   1. Make sure your compliance agent is running")
        print("   2. Trigger some violations")
        print("   3. Check LangSmith UI: https://smith.langchain.com")
    
except Exception as e:
    print(f"❌ Error: {e}")
