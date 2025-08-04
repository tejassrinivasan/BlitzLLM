"""
Modify tool - modifies user questions with various assumptions
"""

import logging
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import Context
from pydantic import Field


# Dictionary of user terms and their clarifications
USER_TERMS_DICTIONARY = {
    "super-star": "players in the top 10% of performance metrics",
    "superstar": "players in the top 10% of performance metrics",
    "star": "players in the top 25% of performance metrics",
    "elite": "players in the top 15% of performance metrics",
    "top-tier": "players in the top 20% of performance metrics",
    "all-star": "players who have been selected for all-star games",
    "mvp": "players with MVP-level performance metrics",
    "rookie": "first-year players",
    "veteran": "players with 5+ years of experience",
    "bench": "players with limited playing time",
    "starter": "players who start regularly",
    "clutch": "players with high performance in critical situations",
    "defensive": "players with strong defensive metrics",
    "offensive": "players with strong offensive metrics",
    "two-way": "players with strong both offensive and defensive metrics",
    "role player": "players with specific specialized roles",
    "franchise player": "players who are the cornerstone of their team",
    "role-player": "players with specific specialized roles",
    "franchise-player": "players who are the cornerstone of their team"
}


async def modify_question(
    ctx: Context,
    original_question: str = Field(..., description="The original user question to modify"),
    assumptions: List[str] = Field(default=[], description="List of assumptions to apply to the question"),
    modification_type: str = Field("clarify", description="Type of modification: 'clarify', 'expand', 'simplify', 'assume'"),
    context: str = Field("", description="Additional context for the modification"),
    limit_results: Optional[int] = Field(None, description="Limit the number of results to return"),
    include_examples: bool = Field(True, description="Whether to include examples in the response"),
    clarify_terms: bool = Field(True, description="Whether to clarify user-specific terms")
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
    logger.info(f"Limit results: {limit_results}")
    logger.info(f"Include examples: {include_examples}")
    logger.info(f"Clarify terms: {clarify_terms}")
    
    try:
        # Start with the original question
        modified_question = original_question
        
        # Apply term clarifications if enabled
        if clarify_terms:
            modified_question = _apply_term_clarifications(modified_question)
        
        # Apply assumptions based on modification type
        if modification_type == "clarify":
            modified_question = _apply_clarifications(modified_question, assumptions, context, limit_results, include_examples)
        elif modification_type == "expand":
            modified_question = _apply_expansions(modified_question, assumptions, context, limit_results, include_examples)
        elif modification_type == "simplify":
            modified_question = _apply_simplifications(modified_question, assumptions, context, limit_results, include_examples)
        elif modification_type == "assume":
            modified_question = _apply_assumptions(modified_question, assumptions, context, limit_results, include_examples)
        else:
            # Default to clarify
            modified_question = _apply_clarifications(modified_question, assumptions, context, limit_results, include_examples)
        
        # Create response with both original and modified questions
        result = {
            "original_question": original_question,
            "modified_question": modified_question,
            "assumptions_applied": assumptions,
            "modification_type": modification_type,
            "context_used": context,
            "limit_results": limit_results,
            "include_examples": include_examples,
            "clarify_terms": clarify_terms,
            "transformation_summary": _generate_transformation_summary(original_question, modified_question, assumptions, limit_results, include_examples)
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


def _apply_term_clarifications(question: str) -> str:
    """Apply clarifications for user-specific terms."""
    modified_question = question
    
    for term, clarification in USER_TERMS_DICTIONARY.items():
        if term.lower() in question.lower():
            # Replace the term with its clarification
            import re
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            modified_question = pattern.sub(f"{term} ({clarification})", modified_question)
    
    return modified_question


def _apply_clarifications(question: str, assumptions: List[str], context: str, limit_results: Optional[int], include_examples: bool) -> str:
    """Apply clarifications to make the question more specific."""
    clarifications = []
    
    # Add context if provided
    if context:
        clarifications.append(f"Context: {context}")
    
    # Add limit if specified
    if limit_results:
        clarifications.append(f"Limit to {limit_results} results")
    
    # Add examples preference
    if not include_examples:
        clarifications.append("Exclude examples")
    elif include_examples:
        clarifications.append("Include examples")
    
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
        elif "limit" in assumption.lower():
            clarifications.append("Limiting results to manageable number")
    
    if clarifications:
        clarification_text = " ".join(clarifications)
        return f"{question} ({clarification_text})"
    
    return question


def _apply_expansions(question: str, assumptions: List[str], context: str, limit_results: Optional[int], include_examples: bool) -> str:
    """Expand the question to be more comprehensive."""
    expansions = []
    
    # Add context if provided
    if context:
        expansions.append(f"Given {context}, ")
    
    # Add limit if specified
    if limit_results:
        expansions.append(f"Limit results to {limit_results} items")
    
    # Add examples preference
    if include_examples:
        expansions.append("Include relevant examples")
    else:
        expansions.append("Focus on data without examples")
    
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
        elif "limit" in assumption.lower():
            expansions.append("Limit scope to manageable results")
    
    if expansions:
        expansion_text = " ".join(expansions)
        return f"{question}. {expansion_text}"
    
    return question


def _apply_simplifications(question: str, assumptions: List[str], context: str, limit_results: Optional[int], include_examples: bool) -> str:
    """Simplify the question to be more focused."""
    simplifications = []
    
    # Add limit if specified
    if limit_results:
        simplifications.append(f"Limit to {limit_results} results")
    
    # Add examples preference
    if not include_examples:
        simplifications.append("No examples needed")
    
    # Apply simplifications based on assumptions
    for assumption in assumptions:
        if "basic" in assumption.lower():
            simplifications.append("Keep it simple")
        elif "focused" in assumption.lower():
            simplifications.append("Focus on key metrics")
        elif "summary" in assumption.lower():
            simplifications.append("Provide summary-level data")
        elif "limit" in assumption.lower():
            simplifications.append("Limit scope")
    
    if simplifications:
        simplification_text = " ".join(simplifications)
        return f"{question} ({simplification_text})"
    
    return question


def _apply_assumptions(question: str, assumptions: List[str], context: str, limit_results: Optional[int], include_examples: bool) -> str:
    """Apply specific assumptions to the question."""
    assumption_texts = []
    
    # Add context if provided
    if context:
        assumption_texts.append(f"Assuming {context}")
    
    # Add limit if specified
    if limit_results:
        assumption_texts.append(f"Assuming limit of {limit_results} results")
    
    # Add examples preference
    if include_examples:
        assumption_texts.append("Assuming examples should be included")
    else:
        assumption_texts.append("Assuming examples should be excluded")
    
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
        elif "limit" in assumption.lower():
            assumption_texts.append("Assuming limited result set")
    
    if assumption_texts:
        assumption_text = " ".join(assumption_texts)
        return f"{question} (Assumptions: {assumption_text})"
    
    return question


def _generate_transformation_summary(original: str, modified: str, assumptions: List[str], limit_results: Optional[int], include_examples: bool) -> str:
    """Generate a summary of the transformation applied."""
    if original == modified:
        return "No modifications applied"
    
    summary_parts = []
    
    if len(assumptions) > 0:
        summary_parts.append(f"Applied {len(assumptions)} assumption(s)")
    
    if limit_results:
        summary_parts.append(f"Limited to {limit_results} results")
    
    if not include_examples:
        summary_parts.append("Excluded examples")
    elif include_examples:
        summary_parts.append("Included examples")
    
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
            "detailed": "Request detailed breakdown",
            "limit": "Limit results to manageable number"
        },
        "expand": {
            "all_sources": "Include all relevant data sources",
            "detailed_analysis": "Provide detailed analysis",
            "comparative": "Include comparative analysis",
            "trend_analysis": "Include trend analysis",
            "limit": "Limit scope to manageable results"
        },
        "simplify": {
            "basic": "Keep it simple",
            "focused": "Focus on key metrics",
            "summary": "Provide summary-level data",
            "limit": "Limit scope"
        },
        "assume": {
            "current_season": "Assume current season data",
            "recent_performance": "Assume recent performance data",
            "healthy_players": "Assume healthy/active players only",
            "regular_season": "Assume regular season data",
            "playoff_data": "Assume playoff data",
            "limit": "Assume limited result set"
        },
        "user_terms": USER_TERMS_DICTIONARY
    }
    
    return {
        "available_presets": presets,
        "usage": "Use these preset keys as assumptions in the modify_question function",
        "new_features": {
            "limit_results": "Specify a number to limit results",
            "include_examples": "Set to false to exclude examples (default: true)",
            "clarify_terms": "Set to false to skip term clarification (default: true)"
        }
    }


async def add_user_term(
    ctx: Context,
    term: str = Field(..., description="The user term to add"),
    clarification: str = Field(..., description="The clarification/definition for this term")
) -> Dict[str, Any]:
    """
    Add a new user term and its clarification to the dictionary.
    
    This allows you to dynamically add new terms that users might use
    and their corresponding clarifications.
    """
    global USER_TERMS_DICTIONARY
    
    USER_TERMS_DICTIONARY[term.lower()] = clarification
    
    return {
        "term_added": term,
        "clarification": clarification,
        "total_terms": len(USER_TERMS_DICTIONARY),
        "message": f"Successfully added '{term}' with clarification: '{clarification}'"
    }


async def get_user_terms() -> Dict[str, Any]:
    """
    Get all currently defined user terms and their clarifications.
    """
    return {
        "user_terms": USER_TERMS_DICTIONARY,
        "total_terms": len(USER_TERMS_DICTIONARY),
        "usage": "These terms will be automatically clarified when found in user questions"
    } 