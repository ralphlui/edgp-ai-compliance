"""
Main LangGraph for Remediation Workflow Orchestration

This module contains the main graph that orchestrates the intelligent
remediation workflow using LangGraph nodes and conditional routing.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig

from ..state.remediation_state import RemediationStateSchema, RemediationStateManager
from ..state.models import (
    RemediationSignal,
    WorkflowStatus,
    RemediationType
)

from .nodes.analysis_node import AnalysisNode
from .nodes.decision_node import DecisionNode
from .nodes.workflow_node import WorkflowNode
from .nodes.execution_node import ExecutionNode
from .nodes.human_loop_node import HumanLoopNode

logger = logging.getLogger(__name__)


class RemediationGraph:
    """
    Main LangGraph for orchestrating intelligent remediation workflows.

    The graph processes compliance violations through a series of intelligent
    nodes that analyze, decide, and execute appropriate remediation strategies.
    """

    def __init__(self) -> None:
        self.state_manager = RemediationStateManager()

        # Initialize nodes
        self.analysis_node = AnalysisNode()
        self.decision_node = DecisionNode()
        self.workflow_node = WorkflowNode()
        self.execution_node = ExecutionNode()
        self.human_loop_node = HumanLoopNode()

        # Build the graph
        self.graph = self._build_graph()

        # Compile with memory for persistence
        self.compiled_graph = self.graph.compile(
            checkpointer=MemorySaver(),
            interrupt_before=["human_loop"]  # Allow manual intervention before human loop
        )

        # Graph visualization removed to reduce noise in logs
        # You can still access the graph via get_graph_visualization() API endpoint

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""

        # Create the graph with our state schema
        workflow = StateGraph(RemediationStateSchema)

        # Add nodes
        workflow.add_node("analyze", self.analysis_node)
        workflow.add_node("decide", self.decision_node)
        workflow.add_node("create_workflow", self.workflow_node)
        workflow.add_node("execute", self.execution_node)
        workflow.add_node("human_loop", self.human_loop_node)
        workflow.add_node("finalize", self._finalize_remediation)

        # Define the flow
        workflow.set_entry_point("analyze")

        # Analysis -> Decision
        workflow.add_edge("analyze", "decide")

        # Decision -> Workflow Creation
        workflow.add_edge("decide", "create_workflow")

        # Conditional routing from workflow creation
        workflow.add_conditional_edges(
            "create_workflow",
            self._route_after_workflow_creation,
            {
                "human_intervention": "human_loop",
                "automatic_execution": "execute",
                "error": END
            }
        )

        # Execution -> Finalize (for automatic workflows)
        workflow.add_edge("execute", "finalize")

        # Human loop -> Finalize
        workflow.add_edge("human_loop", "finalize")

        # Finalize -> End
        workflow.add_edge("finalize", END)

        return workflow

    async def process_remediation_signal(
        self,
        signal: RemediationSignal,
        config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """
        Process a remediation signal through the complete workflow

        Args:
            signal: The compliance violation signal to process
            config: Optional configuration for the execution

        Returns:
            Dictionary containing the execution results
        """
        logger.info(f"🔄 [GRAPH-PROCESS-START] Processing remediation signal for violation {signal.violation.rule_id}")
        logger.info(f"📡 [SIGNAL-INPUT] Signal for violation: {signal.violation.rule_id}, Priority: {signal.urgency.value}")
        logger.info(f"🎯 [SIGNAL-TARGET] Violation: {signal.violation.rule_id}, Activity: {signal.activity.id}")

        try:
            # Create initial state
            logger.info(f"🌱 [STATE-CREATE] Creating initial state for {signal.violation.rule_id}")
            initial_state = self.state_manager.create_initial_state(signal)
            logger.info(f"✅ [STATE-CREATED] Initial state keys: {list(initial_state.keys())}")

            # Execute the graph
            execution_config = config or {"configurable": {"thread_id": f"remediation_{signal.violation.rule_id}"}}
            logger.info(f"⚙️ [EXECUTION-CONFIG] Thread ID: {execution_config['configurable']['thread_id']}")

            final_state = None
            execution_steps = []

            # Execute the graph and collect the final state properly
            final_state_values = None
            execution_steps = []

            logger.info(f"🚀 [GRAPH-EXECUTION-START] Starting LangGraph compiled workflow execution")
            step_count = 0
            async for step in self.compiled_graph.astream(initial_state, execution_config):
                step_count += 1
                timestamp = datetime.now(timezone.utc).isoformat()
                node_name = list(step.keys())[0] if step else "unknown"

                logger.info(f"🔄 [STEP-{step_count:02d}] Executing node: {node_name}")
                logger.info(f"⏰ [STEP-TIMESTAMP] {timestamp}")

                execution_steps.append({
                    "timestamp": timestamp,
                    "step": step,
                    "node": node_name,
                    "step_number": step_count
                })

                # Extract the state properly from each step
                if step and isinstance(step, dict):
                    # Get the node name and its state
                    node_name = list(step.keys())[0]
                    node_state = step[node_name]

                    # Handle interrupt nodes specially
                    if node_name == "__interrupt__":
                        logger.info(f"⏸️ [INTERRUPT] Graph interrupted before next node")
                        # For interrupts, the node_state might be a tuple or other type
                        # We should keep the previous valid state and continue
                        if isinstance(node_state, tuple):
                            logger.info(f"📊 [INTERRUPT-TUPLE] Interrupt state is tuple: {type(node_state)}")
                            # Skip processing this interrupt step, keep previous state
                            continue
                        elif not isinstance(node_state, dict):
                            logger.info(f"📊 [INTERRUPT-OTHER] Interrupt state type: {type(node_state)}")
                            continue

                    logger.info(f"📊 [NODE-OUTPUT] {node_name} completed")
                    if isinstance(node_state, dict):
                        logger.info(f"🔍 [NODE-STATE-KEYS] {list(node_state.keys())}")

                    # Store the latest valid state
                    if isinstance(node_state, dict):
                        final_state_values = node_state
                    else:
                        logger.warning(f"Node {node_name} returned non-dict state: {type(node_state)}")

            # Ensure we have a valid final state
            if not final_state_values or not isinstance(final_state_values, dict):
                logger.error(f"No valid final state found. Using fallback state.")
                final_state_values = {
                    "signal": initial_state["signal"],
                    "errors": ["Invalid final state - using fallback"],
                    "execution_path": ["fallback_state_created"],
                    "context": {},
                    "decision": None,
                    "workflow": None
                }

            # Prepare execution summary
            execution_summary = self._create_execution_summary(
                final_state_values, execution_steps, signal
            )

            logger.info(f"Remediation processing complete for {signal.violation.rule_id}")

            return execution_summary

        except Exception as e:
            logger.error(f"Error processing remediation signal: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "violation_id": signal.violation.rule_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _route_after_workflow_creation(self, state: RemediationStateSchema) -> str:
        """Route the workflow after creation based on decision type"""

        # Check for errors first
        if state.get("errors") and any("critical" in error.lower() for error in state["errors"]):
            return "error"

        # Check if human intervention is required
        decision = state.get("decision")
        if not decision:
            return "error"

        if decision.remediation_type in [RemediationType.HUMAN_IN_LOOP, RemediationType.MANUAL_ONLY]:
            return "human_intervention"
        else:
            return "automatic_execution"

    async def _finalize_remediation(self, state: RemediationStateSchema) -> RemediationStateSchema:
        """Finalize the remediation process"""

        logger.info(f"Finalizing remediation for violation {state['signal'].violation.rule_id}")

        try:
            state["execution_path"].append("finalization_started")

            # Update workflow status
            workflow = state.get("workflow")
            if workflow:
                # Determine final status
                if state.get("errors"):
                    workflow.status = WorkflowStatus.FAILED
                elif state.get("requires_human") and not self.human_loop_node.is_human_intervention_complete(state):
                    workflow.status = WorkflowStatus.REQUIRES_HUMAN
                else:
                    workflow.status = WorkflowStatus.COMPLETED
                    workflow.completed_at = datetime.now(timezone.utc)

                state["workflow_status"] = workflow.status

            # Update state manager
            if workflow:
                self.state_manager.update_workflow_status(state, workflow.status)

            # Calculate execution metrics
            execution_metrics = self._calculate_execution_metrics(state)
            state["context"]["execution_metrics"] = execution_metrics

            # Final logging
            state["execution_path"].append("finalization_completed")

            logger.info(f"Remediation finalized: {workflow.status if workflow else 'no_workflow'}")

            return state

        except Exception as e:
            logger.error(f"Error in finalization: {str(e)}")
            state["errors"].append(f"Finalization error: {str(e)}")
            state["execution_path"].append("finalization_failed")
            return state

    def _create_execution_summary(
        self,
        final_state: RemediationStateSchema,
        execution_steps: List[Dict[str, Any]],
        signal: RemediationSignal
    ) -> Dict[str, Any]:
        """Create a comprehensive execution summary"""

        # Ensure final_state is a dictionary
        if not isinstance(final_state, dict):
            logger.warning(f"Final state is not a dictionary: {type(final_state)}")
            final_state = {"errors": ["Invalid final state format"], "execution_path": []}

        decision = final_state.get("decision")
        workflow = final_state.get("workflow")
        context = final_state.get("context", {})

        summary = {
            "success": len(final_state.get("errors", [])) == 0,
            "violation_id": signal.violation.rule_id,
            "processing_timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_path": final_state.get("execution_path", []),
            "total_execution_steps": len(execution_steps),
            "errors": final_state.get("errors", []),
            "warnings": [],  # Could be extracted from logs

            # Signal information
            "signal_info": {
                "framework": signal.framework,
                "urgency": signal.urgency.value,
                "data_types": [dt.value for dt in signal.activity.data_types],
                "cross_border_transfers": signal.activity.cross_border_transfers,
                "automated_decision_making": signal.activity.automated_decision_making
            },

            # Analysis results
            "analysis_results": {
                "complexity_assessment": final_state.get("complexity_assessment", {}),
                "feasibility_score": final_state.get("feasibility_score", 0.0)
            },

            # Decision information
            "decision_info": {
                "remediation_type": decision.remediation_type.value if decision else "unknown",
                "confidence_score": decision.confidence_score if decision else 0.0,
                "estimated_effort": decision.estimated_effort if decision else 0,
                "reasoning": decision.reasoning if decision else "No decision made"
            } if decision else {},

            # Workflow information
            "workflow_info": self.workflow_node.get_workflow_summary(final_state) if workflow else {},

            # Human loop information
            "human_loop_info": self.human_loop_node.get_human_loop_summary(final_state),

            # Execution context
            "execution_context": context,

            # Next steps
            "next_steps": self._determine_next_steps(final_state),

            # Metrics
            "metrics": context.get("execution_metrics", {})
        }

        return summary

    def _calculate_execution_metrics(self, state: RemediationStateSchema) -> Dict[str, Any]:
        """Calculate execution metrics"""

        context = state.get("context", {})
        start_time = context.get("started_at")

        metrics = {
            "execution_time_seconds": 0,
            "nodes_executed": len(state.get("execution_path", [])),
            "errors_encountered": len(state.get("errors", [])),
            "human_intervention_required": state.get("requires_human", False),
            "workflow_created": context.get("workflow_created", False),
            "sqs_queue_created": state.get("sqs_queue_created", False),
            "notifications_sent": context.get("notifications_sent", 0)
        }

        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                execution_time = (datetime.now(timezone.utc) - start_dt).total_seconds()
                metrics["execution_time_seconds"] = execution_time
            except (ValueError, TypeError):
                pass

        return metrics

    def _determine_next_steps(self, state: RemediationStateSchema) -> List[str]:
        """Determine next steps based on final state"""

        next_steps = []

        workflow = state.get("workflow")
        decision = state.get("decision")

        if state.get("errors"):
            next_steps.append("Investigate and resolve errors")

        if state.get("requires_human"):
            if decision and decision.remediation_type == RemediationType.MANUAL_ONLY:
                next_steps.append("Complete manual remediation tasks")
            else:
                next_steps.append("Complete human review and approval")

        if workflow and workflow.status == WorkflowStatus.IN_PROGRESS:
            next_steps.append("Monitor workflow execution progress")

        if workflow and workflow.status == WorkflowStatus.COMPLETED:
            next_steps.extend([
                "Verify compliance resolution",
                "Update compliance tracking systems",
                "Archive workflow documentation"
            ])

        if not next_steps:
            next_steps.append("Remediation process complete")

        return next_steps

    async def get_workflow_status(
        self,
        violation_id: str
    ) -> Dict[str, Any]:
        """Get the current status of a workflow"""

        # In a production system, this would query the state from persistence
        # For now, we'll return status from the state manager

        workflow_summary = self.state_manager.get_workflow_summary(violation_id)

        if workflow_summary:
            return {
                "found": True,
                "workflow_summary": workflow_summary,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            return {
                "found": False,
                "violation_id": violation_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def resume_workflow(
        self,
        violation_id: str,
        config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """Resume a paused or interrupted workflow"""

        logger.info(f"Resuming workflow for violation {violation_id}")

        try:
            # Get the execution config
            execution_config = config or {"configurable": {"thread_id": f"remediation_{violation_id}"}}

            # Resume execution from where it was interrupted
            final_state = None
            async for step in self.compiled_graph.astream(None, execution_config):
                final_state = step

            return {
                "success": True,
                "violation_id": violation_id,
                "resumed": True,
                "final_state": final_state,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error resuming workflow for {violation_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "violation_id": violation_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def build_graph(self) -> StateGraph:
        """Public method to access the compiled graph structure.
        
        Returns:
            StateGraph: The compiled LangGraph state graph
        """
        return self.graph

    def print_graph_ascii(self) -> str:
        """Print ASCII representation of the graph (requires grandalf)"""
        try:
            return self.graph.get_graph().draw_ascii()
        except Exception as e:
            logger.warning("Could not display graph ASCII: %s", e)
            return "Graph visualization unavailable (install grandalf: pip install grandalf)"

    def get_graph_ascii(self) -> str:
        """Get the ASCII representation of the graph as a string"""
        try:
            return self.compiled_graph.get_graph().draw_ascii()
        except Exception as e:
            logger.warning(f"Could not generate graph ASCII: {str(e)}")
            return f"Graph ASCII unavailable: {str(e)}"

    def get_graph_visualization(self) -> Dict[str, Any]:
        """Get a visualization representation of the graph"""

        # Include ASCII representation in the visualization data
        ascii_representation = self.get_graph_ascii()

        return {
            "ascii_graph": ascii_representation,
            "nodes": [
                {"id": "analyze", "label": "Analysis Node", "type": "analysis"},
                {"id": "decide", "label": "Decision Node", "type": "decision"},
                {"id": "create_workflow", "label": "Workflow Node", "type": "workflow"},
                {"id": "human_loop", "label": "Human Loop Node", "type": "human"},
                {"id": "finalize", "label": "Finalize Node", "type": "finalize"}
            ],
            "edges": [
                {"from": "analyze", "to": "decide", "label": "analysis_complete"},
                {"from": "decide", "to": "create_workflow", "label": "decision_made"},
                {"from": "create_workflow", "to": "human_loop", "label": "human_intervention", "conditional": True},
                {"from": "create_workflow", "to": "finalize", "label": "automatic_execution", "conditional": True},
                {"from": "human_loop", "to": "finalize", "label": "human_complete"},
                {"from": "finalize", "to": "END", "label": "process_complete"}
            ],
            "conditional_nodes": ["create_workflow"],
            "entry_point": "analyze",
            "description": "Intelligent remediation workflow with analysis, decision-making, and human-in-the-loop capabilities"
        }
