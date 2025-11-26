"""
LangSmith Evaluators for Compliance Agent

Custom evaluators to assess compliance analysis quality.
"""

from langsmith.evaluation import EvaluationResult
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.schema import HumanMessage
from numpy import dot
from numpy.linalg import norm
import json
from typing import Any


# ============================================================================
# 1. EXACT MATCH EVALUATORS
# ============================================================================

def exact_urgency_match(run, example) -> EvaluationResult:
    """
    Check if urgency level matches expected value exactly
    
    Score: 1.0 if exact match, 0.0 otherwise
    """
    predicted = run.outputs.get("urgency_level", "").upper()
    expected = example.outputs.get("urgency_level", "").upper()
    
    score = 1.0 if predicted == expected else 0.0
    
    return EvaluationResult(
        key="exact_urgency_match",
        score=score,
        comment=f"Predicted: {predicted}, Expected: {expected}"
    )


# ============================================================================
# 2. SUBSTRING / PATTERN MATCH EVALUATORS
# ============================================================================

def legal_reference_present(run, example) -> EvaluationResult:
    """
    Check if appropriate legal reference is mentioned
    
    Score: 1.0 if valid reference found, 0.0 otherwise
    """
    output = run.outputs.get("legal_reference", "")
    framework = example.inputs.get("framework", "")
    
    # Check for framework-specific references
    if framework == "PDPA":
        has_reference = "PDPA" in output and ("Article" in output or "Section" in output)
    elif framework == "GDPR":
        has_reference = "GDPR" in output and "Article" in output
    else:
        has_reference = False
    
    score = 1.0 if has_reference else 0.0
    
    return EvaluationResult(
        key="legal_reference_present",
        score=score,
        comment=f"Framework: {framework}, Reference valid: {has_reference}"
    )


def description_contains_key_facts(run, example) -> EvaluationResult:
    """
    Check if description mentions key violation facts
    
    Score: Percentage of key facts mentioned (0.0 to 1.0)
    """
    description = run.outputs.get("description", "").lower()
    inputs = example.inputs
    
    # Key facts that should be mentioned
    facts_to_check = [
        str(inputs.get("data_age_days", "")),  # Data age
        str(inputs.get("excess_days", "")),     # Excess days
        inputs.get("framework", "").lower(),    # Framework name
    ]
    
    facts_found = sum(1 for fact in facts_to_check if fact in description)
    score = facts_found / len(facts_to_check)
    
    return EvaluationResult(
        key="key_facts_present",
        score=score,
        comment=f"Found {facts_found}/{len(facts_to_check)} key facts in description"
    )


# ============================================================================
# 3. BUSINESS LOGIC EVALUATORS
# ============================================================================

def urgency_level_correctness(run, example) -> EvaluationResult:
    """
    Check if urgency level follows business rules
    
    Business Rules:
    - HIGH: > 5000 days excess
    - MEDIUM: 1000-5000 days excess
    - LOW: < 1000 days excess
    
    Score: 1.0 if correct, 0.0 otherwise
    """
    excess_days = example.inputs.get("excess_days", 0)
    predicted_urgency = run.outputs.get("urgency_level", "").upper()
    
    # Apply business rules
    if excess_days > 5000:
        expected = "HIGH"
    elif excess_days >= 1000:
        expected = "MEDIUM"
    else:
        expected = "LOW"
    
    correct = (predicted_urgency == expected)
    score = 1.0 if correct else 0.0
    
    return EvaluationResult(
        key="urgency_correctness",
        score=score,
        comment=f"Excess: {excess_days} days → Expected: {expected}, Got: {predicted_urgency}"
    )


def recommendation_actionable(run, example) -> EvaluationResult:
    """
    Check if recommendation contains actionable verbs
    
    Score: 1.0 if actionable, 0.5 if partial, 0.0 if vague
    """
    recommendation = run.outputs.get("recommendation", "").lower()
    
    # Actionable verbs for compliance
    actionable_verbs = [
        "delete", "remove", "purge", "anonymize", "archive",
        "implement", "schedule", "review", "update", "conduct"
    ]
    
    verbs_found = sum(1 for verb in actionable_verbs if verb in recommendation)
    
    if verbs_found >= 2:
        score = 1.0
        comment = f"Found {verbs_found} actionable verbs (excellent)"
    elif verbs_found == 1:
        score = 0.5
        comment = f"Found {verbs_found} actionable verb (acceptable)"
    else:
        score = 0.0
        comment = "No actionable verbs found (too vague)"
    
    return EvaluationResult(
        key="recommendation_actionable",
        score=score,
        comment=comment
    )


# ============================================================================
# 4. SEMANTIC SIMILARITY EVALUATORS
# ============================================================================

def semantic_similarity_description(run, example) -> EvaluationResult:
    """
    Calculate semantic similarity between predicted and expected descriptions
    
    Score: Cosine similarity (0.0 to 1.0)
    """
    try:
        embeddings = OpenAIEmbeddings()
        
        predicted = run.outputs.get("description", "")
        expected = example.outputs.get("description", "")
        
        if not predicted or not expected:
            return EvaluationResult(
                key="semantic_similarity",
                score=0.0,
                comment="Missing description"
            )
        
        # Get embeddings
        pred_embedding = embeddings.embed_query(predicted)
        exp_embedding = embeddings.embed_query(expected)
        
        # Calculate cosine similarity
        similarity = dot(pred_embedding, exp_embedding) / (
            norm(pred_embedding) * norm(exp_embedding)
        )
        
        return EvaluationResult(
            key="semantic_similarity",
            score=float(similarity),
            comment=f"Cosine similarity: {similarity:.3f}"
        )
    except Exception as e:
        return EvaluationResult(
            key="semantic_similarity",
            score=0.0,
            comment=f"Error calculating similarity: {str(e)}"
        )


# ============================================================================
# 5. LLM-AS-JUDGE EVALUATORS
# ============================================================================

def llm_judge_compliance_quality(run, example) -> EvaluationResult:
    """
    Use GPT-4 to judge overall compliance analysis quality
    
    Score: 0.0 to 1.0 based on GPT-4's assessment
    """
    try:
        judge_llm = ChatOpenAI(model="gpt-4", temperature=0)
        
        predicted_description = run.outputs.get("description", "")
        predicted_recommendation = run.outputs.get("recommendation", "")
        predicted_reference = run.outputs.get("legal_reference", "")
        inputs = example.inputs
        
        judge_prompt = f"""
You are a compliance expert evaluating an AI-generated compliance analysis.

VIOLATION DATA:
- Data Age: {inputs['data_age_days']} days
- Retention Limit: {inputs['retention_limit_days']} days
- Excess Days: {inputs['excess_days']} days
- Framework: {inputs['framework']}
- Region: {inputs['region']}

AI-GENERATED ANALYSIS:
Description: {predicted_description}
Recommendation: {predicted_recommendation}
Legal Reference: {predicted_reference}

EVALUATION CRITERIA:
1. Accuracy: Does it correctly identify the violation?
2. Completeness: Does it mention all relevant details (excess days, framework)?
3. Clarity: Is it easy to understand?
4. Legal Grounding: Does it reference appropriate regulations?
5. Actionability: Are recommendations specific and implementable?

Provide a score from 0.0 to 1.0:
- 1.0 = Excellent (all criteria strongly met)
- 0.8 = Good (most criteria met well)
- 0.6 = Acceptable (some criteria met)
- 0.4 = Poor (few criteria met)
- 0.2 = Very Poor (minimal criteria met)
- 0.0 = Unacceptable (no criteria met)

Return ONLY a JSON object:
{{"score": <float>, "reasoning": "<brief explanation>"}}
"""
        
        response = judge_llm.invoke([HumanMessage(content=judge_prompt)])
        
        result = json.loads(response.content)
        score = result.get("score", 0.0)
        reasoning = result.get("reasoning", "No reasoning provided")
        
        return EvaluationResult(
            key="llm_judge_quality",
            score=score,
            comment=reasoning
        )
    
    except Exception as e:
        return EvaluationResult(
            key="llm_judge_quality",
            score=0.0,
            comment=f"Error in LLM judge: {str(e)}"
        )


# ============================================================================
# 6. COMPOSITE EVALUATORS
# ============================================================================

def comprehensive_compliance_score(run, example) -> EvaluationResult:
    """
    Aggregate score from multiple evaluators
    
    Score: Weighted average of all evaluators
    """
    evaluators = {
        "exact_urgency": (exact_urgency_match, 0.20),           # 20% weight
        "legal_reference": (legal_reference_present, 0.20),     # 20% weight
        "urgency_business": (urgency_level_correctness, 0.15),  # 15% weight
        "key_facts": (description_contains_key_facts, 0.15),    # 15% weight
        "actionable": (recommendation_actionable, 0.15),        # 15% weight
        "semantic": (semantic_similarity_description, 0.15),    # 15% weight
    }
    
    total_score = 0.0
    total_weight = 0.0
    results = {}
    
    for name, (evaluator, weight) in evaluators.items():
        try:
            result = evaluator(run, example)
            total_score += result.score * weight
            total_weight += weight
            results[name] = result.score
        except Exception as e:
            results[name] = 0.0
    
    final_score = total_score / total_weight if total_weight > 0 else 0.0
    
    return EvaluationResult(
        key="comprehensive_score",
        score=final_score,
        comment=f"Weighted average: {final_score:.3f}",
        metadata={"individual_scores": results}
    )


# ============================================================================
# EVALUATOR REGISTRY
# ============================================================================

# All available evaluators
ALL_EVALUATORS = [
    exact_urgency_match,
    legal_reference_present,
    description_contains_key_facts,
    urgency_level_correctness,
    recommendation_actionable,
    semantic_similarity_description,
    llm_judge_compliance_quality,
    comprehensive_compliance_score
]

# Fast evaluators (no LLM calls, no embeddings)
FAST_EVALUATORS = [
    exact_urgency_match,
    legal_reference_present,
    description_contains_key_facts,
    urgency_level_correctness,
    recommendation_actionable
]

# Quality evaluators (includes LLM judge)
QUALITY_EVALUATORS = [
    llm_judge_compliance_quality,
    semantic_similarity_description,
    comprehensive_compliance_score
]


if __name__ == "__main__":
    print("\n" + "="*80)
    print("LANGSMITH EVALUATORS")
    print("="*80)
    print(f"\n📊 Total Evaluators: {len(ALL_EVALUATORS)}")
    print(f"⚡ Fast Evaluators: {len(FAST_EVALUATORS)}")
    print(f"🎯 Quality Evaluators: {len(QUALITY_EVALUATORS)}")
    print("\nEvaluators registered:")
    for evaluator in ALL_EVALUATORS:
        print(f"  - {evaluator.__name__}")
