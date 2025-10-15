#!/usr/bin/env python3
"""
Application entry point
Run the AI Compliance Agent API server with integrated Remediation Service
"""

import argparse
import uvicorn
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from config.settings import settings


def print_service_banner():
    """Print service startup banner"""
    print("🚀 " + "="*70)
    print("🔧 AI COMPLIANCE AGENT WITH REMEDIATION SERVICE")
    print("="*72)
    print()
    print("📋 Service Information:")
    print(f"   • Service: {settings.app_name}")
    print(f"   • Version: {settings.app_version}")
    print("   • Framework: FastAPI + LangGraph")
    print(f"   • AI Engine: {settings.ai_model_name}")
    print("   • Remediation: Enabled" if settings.remediation_agent_enabled else "   • Remediation: Disabled")
    print()


def print_startup_info():
    """Print startup configuration"""
    print("⚙️  Configuration:")
    print(f"   • Environment: {settings.app_env}")
    print(f"   • Host: {settings.api_host}")
    print(f"   • Port: {settings.api_port}")
    print(f"   • Workers: {settings.api_workers if not settings.debug else 1}")
    print(f"   • Debug Mode: {settings.debug}")
    print(f"   • Log Level: {settings.log_level}")
    print()

    # AI Agent API status
    if settings.ai_agent_api_key:
        print("   ✅ AI Agent API Key: Configured")
    elif settings.openai_api_key:
        print("   ✅ OpenAI API Key: Configured (legacy)")
    else:
        print("   ❌ AI API Key: Not configured")

    # AWS/SQS status
    if settings.aws_access_key_id:
        print("   ✅ AWS Credentials: Configured")
        print(f"   🌍 AWS Region: {settings.aws_region}")
    else:
        print("   ⚠️  AWS Credentials: Using mock mode")

    # Remediation status
    if settings.remediation_agent_enabled:
        print("   ✅ Remediation Agent: Enabled")
        print(f"   📊 Max Concurrent Workflows: {settings.remediation_max_concurrent_workflows}")
    else:
        print("   ⚠️  Remediation Agent: Disabled")

    print()
    print("🔄 Background Processing:")
    print("   ✅ Automatic Compliance Scanning: Every 5 minutes")
    print("   🔍 Frameworks: PDPA (Singapore) + GDPR (EU)")
    print("   📊 Look for 'AUTOMATIC COMPLIANCE SCAN #X' in logs")
    print()


def print_endpoints():
    """Print available endpoints"""
    print("🌐 Available Endpoints:")
    print(f"   • Service Info:     GET  http://{settings.api_host}:{settings.api_port}/")
    print(f"   • Health Check:     GET  http://{settings.api_host}:{settings.api_port}/health")
    print(f"   • API Docs:         GET  http://{settings.api_host}:{settings.api_port}/docs")
    print()
    print("📋 Compliance Endpoints:")
    print("   • Privacy Check:    POST /api/v1/privacy/assess")
    print("   • Compliance Check: POST /api/v1/compliance/check")
    print("   • Governance:       POST /api/v1/governance/evaluate")
    print()

    if settings.remediation_agent_enabled:
        print("🔧 Remediation Endpoints:")
        print("   • Trigger:          POST /api/v1/remediation/trigger")
        print("   • Check Status:     GET  /api/v1/remediation/status/{request_id}")
        print("   • Resume Workflow:  POST /api/v1/remediation/resume/{request_id}")
        print("   • Emergency Stop:   DEL  /api/v1/remediation/stop/{request_id}")
        print("   • Get Metrics:      GET  /api/v1/remediation/metrics")
        print("   • Graph Viz:        GET  /api/v1/remediation/graph")
    print()


def print_post_startup():
    """Print post-startup information"""
    print("🎉 SERVICE STARTED SUCCESSFULLY!")
    print("="*72)
    print(f"🌐 Server running at: http://{settings.api_host}:{settings.api_port}")
    print(f"📖 API Documentation: http://{settings.api_host}:{settings.api_port}/docs")
    print(f"🔍 Health Check: http://{settings.api_host}:{settings.api_port}/health")
    print()
    print("🛑 To stop the service: Press Ctrl+C")
    print("="*72)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="AI Compliance Agent with Remediation Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                        # Start with default settings
  python main.py --port 8080                           # Start on port 8080
  python main.py --debug                               # Start in debug mode
  python main.py --app-env production                  # Use production environment
  python main.py --aws-region ap-southeast-1          # Set AWS region
  python main.py --ai-agent-api-key your_key_here     # Set AI API key
        """
    )

    parser.add_argument(
        "--host",
        type=str,
        default=settings.api_host,
        help=f"Host to bind (default: {settings.api_host})"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=settings.api_port,
        help=f"Port to bind (default: {settings.api_port})"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=settings.api_workers,
        help=f"Number of worker processes (default: {settings.api_workers})"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=settings.debug,
        help="Enable debug mode with auto-reload"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=settings.log_level,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=f"Log level (default: {settings.log_level})"
    )

    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress startup banner"
    )

    # Environment Configuration Arguments
    parser.add_argument(
        "--app-env",
        type=str,
        help="Application environment (development, sit, production, etc.)"
    )

    parser.add_argument(
        "--aws-region",
        type=str,
        help="AWS region (e.g., us-east-1, ap-southeast-1)"
    )

    parser.add_argument(
        "--aws-access-key-id",
        type=str,
        help="AWS Access Key ID"
    )

    parser.add_argument(
        "--aws-secret-access-key",
        type=str,
        help="AWS Secret Access Key"
    )

    parser.add_argument(
        "--ai-agent-api-key",
        type=str,
        help="AI Agent API Key (OpenAI, Azure OpenAI, etc.)"
    )

    return parser.parse_args()


def main():
    """Main application entry point"""
    args = parse_arguments()

    # Set environment variables from command line arguments if provided
    if args.app_env:
        os.environ["APP_ENV"] = args.app_env
    if args.aws_region:
        os.environ["AWS_REGION"] = args.aws_region
    if args.aws_access_key_id:
        os.environ["AWS_ACCESS_KEY_ID"] = args.aws_access_key_id
    if args.aws_secret_access_key:
        os.environ["AWS_SECRET_ACCESS_KEY"] = args.aws_secret_access_key
    if args.ai_agent_api_key:
        os.environ["AI_AGENT_API_KEY"] = args.ai_agent_api_key

    # Reload settings after setting environment variables if any env vars were set
    if (args.app_env or args.aws_region or args.aws_access_key_id or 
        args.aws_secret_access_key or args.ai_agent_api_key):
        from config.settings import create_settings
        global settings
        settings = create_settings()
        print(f"🔄 Reloaded configuration with environment: {settings.app_env}")

    # Override settings with command line arguments
    host = args.host
    port = args.port
    workers = args.workers if not args.debug else 1
    debug = args.debug
    log_level = args.log_level.lower()

    if not args.no_banner:
        print_service_banner()
        print_startup_info()
        print_endpoints()

    try:
        print("🚀 Starting FastAPI server...")

        uvicorn.run(
            "compliance_agent.api.main:app",
            host=host,
            port=port,
            workers=workers,
            reload=debug,
            log_level=log_level,
            access_log=True,
            loop="auto"
        )

    except KeyboardInterrupt:
        print("\n🛑 Service stopped by user")
    except Exception as e:
        print(f"\n❌ Service failed to start: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()