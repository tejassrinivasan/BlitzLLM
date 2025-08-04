"""
Modify tool - modifies user questions with various assumptions
"""

import logging
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import Context
from pydantic import Field


async def modify_question(
    ctx: Context,
    original_question: str = Field(..., description="The original user question to modify"),
    assumptions: List[str] = Field(default=[], description="List of assumptions to apply to the question"),
    modification_type: str = Field("clarify", description="Type of modification: 'clarify', 'expand', 'simplify', 'assume'"),
    context: str = Field("", description="Additional context for the modification")
) -> Dict[str, Any]:
    """
    Modify a user's question with various assumptions and clarifications.
    
    This tool helps transform vague or incomplete questions into more specific,
    actionable queries by applying assumptions and clarifications.
    """
    logger = logging.getLogger("blitz-agent-mcp")
    logger.info("=== MODIFY QUESTION DEBUG ===")
    logger.info(f"Original question: {original_question}")
    logger.info(f"Assumptions: {assumptions}")
    logger.info(f"Modification type: {modification_type}")
    logger.info(f"Context: {context}")
    
    try:
        # Start with the original question
        modified_question = original_question
        
        # Apply assumptions based on modification type
        if modification_type == "clarify":
            modified_question = _apply_clarifications(original_question, assumptions, context)
        elif modification_type == "expand":
            modified_question = _apply_expansions(original_question, assumptions, context)
        elif modification_type == "simplify":
            modified_question = _apply_simplifications(original_question, assumptions, context)
        elif modification_type == "assume":
            modified_question = _apply_assumptions(original_question, assumptions, context)
        else:
            # Default to clarify
            modified_question = _apply_clarifications(original_question, assumptions, context)
        
        # Create response with both original and modified questions
        result = {
            "original_question": original_question,
            "modified_question": modified_question,
            "assumptions_applied": assumptions,
            "modification_type": modification_type,
            "context_used": context,
            "transformation_summary": _generate_transformation_summary(original_question, modified_question, assumptions)
        }
        
        logger.info(f"Modified question: {modified_question}")
        logger.info(f"Transformation summary: {result['transformation_summary']}")
        
        return result
        
    except Exception as e:
        logger.error(f"ERROR in modify_question: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise


def _apply_clarifications(question: str, assumptions: List[str], context: str) -> str:
    """Apply clarifications to make the question more specific."""
    clarifications = []
    
    # Add context if provided
    if context:
        clarifications.append(f"Context: {context}")
    
    # Apply specific clarifications based on assumptions
    for assumption in assumptions:
        if "recent" in assumption.lower():
            clarifications.append("Focusing on recent data (last 2-3 years)")
        elif "top" in assumption.lower():
            clarifications.append("Focusing on top performers")
        elif "trend" in assumption.lower():
            clarifications.append("Looking for trends over time")
        elif "comparison" in assumption.lower():
            clarifications.append("Including comparative analysis")
        elif "detailed" in assumption.lower():
            clarifications.append("Requesting detailed breakdown")
    
    if clarifications:
        clarification_text = " ".join(clarifications)
        return f"{question} ({clarification_text})"
    
    return question


def _apply_expansions(question: str, assumptions: List[str], context: str) -> str:
    """Expand the question to be more comprehensive."""
    expansions = []
    
    # Add context if provided
    if context:
        expansions.append(f"Given {context}, ")
    
    # Apply expansions based on assumptions
    for assumption in assumptions:
        if "all" in assumption.lower():
            expansions.append("Include all relevant data sources")
        elif "detailed" in assumption.lower():
            expansions.append("Provide detailed analysis")
        elif "comparison" in assumption.lower():
            expansions.append("Include comparative analysis")
        elif "trends" in assumption.lower():
            expansions.append("Include trend analysis")
    
    if expansions:
        expansion_text = " ".join(expansions)
        return f"{question}. {expansion_text}"
    
    return question


def _apply_simplifications(question: str, assumptions: List[str], context: str) -> str:
    """Simplify the question to be more focused."""
    simplifications = []
    
    # Apply simplifications based on assumptions
    for assumption in assumptions:
        if "basic" in assumption.lower():
            simplifications.append("Keep it simple")
        elif "focused" in assumption.lower():
            simplifications.append("Focus on key metrics")
        elif "summary" in assumption.lower():
            simplifications.append("Provide summary-level data")
    
    if simplifications:
        simplification_text = " ".join(simplifications)
        return f"{question} ({simplification_text})"
    
    return question


def _apply_assumptions(question: str, assumptions: List[str], context: str) -> str:
    """Apply specific assumptions to the question."""
    assumption_texts = []
    
    # Add context if provided
    if context:
        assumption_texts.append(f"Assuming {context}")
    
    # Apply specific assumptions
    for assumption in assumptions:
        if "current" in assumption.lower():
            assumption_texts.append("Assuming current season data")
        elif "recent" in assumption.lower():
            assumption_texts.append("Assuming recent performance data")
        elif "healthy" in assumption.lower():
            assumption_texts.append("Assuming healthy/active players only")
        elif "regular" in assumption.lower():
            assumption_texts.append("Assuming regular season data")
        elif "playoff" in assumption.lower():
            assumption_texts.append("Assuming playoff data")
    
    if assumption_texts:
        assumption_text = " ".join(assumption_texts)
        return f"{question} (Assumptions: {assumption_text})"
    
    return question


def _generate_transformation_summary(original: str, modified: str, assumptions: List[str]) -> str:
    """Generate a summary of the transformation applied."""
    if original == modified:
        return "No modifications applied"
    
    summary_parts = []
    
    if len(assumptions) > 0:
        summary_parts.append(f"Applied {len(assumptions)} assumption(s)")
    
    if len(modified) > len(original):
        summary_parts.append("Question expanded")
    elif len(modified) < len(original):
        summary_parts.append("Question simplified")
    else:
        summary_parts.append("Question clarified")
    
    return "; ".join(summary_parts)


async def get_modification_presets() -> Dict[str, Any]:
    """
    Get available modification presets that can be used as assumptions.
    """
    presets = {
        "clarify": {
            "recent": "Focus on recent data (last 2-3 years)",
            "top_performers": "Focus on top performers only",
            "trends": "Look for trends over time",
            "comparison": "Include comparative analysis",
            "detailed": "Request detailed breakdown"
        },
        "expand": {
            "all_sources": "Include all relevant data sources",
            "detailed_analysis": "Provide detailed analysis",
            "comparative": "Include comparative analysis",
            "trend_analysis": "Include trend analysis"
        },
        "simplify": {
            "basic": "Keep it simple",
            "focused": "Focus on key metrics",
            "summary": "Provide summary-level data"
        },
        "assume": {
            "current_season": "Assume current season data",
            "recent_performance": "Assume recent performance data",
            "healthy_players": "Assume healthy/active players only",
            "regular_season": "Assume regular season data",
            "playoff_data": "Assume playoff data"
        }
    }
    
    return {
        "available_presets": presets,
        "usage": "Use these preset keys as assumptions in the modify_question function"
    } 