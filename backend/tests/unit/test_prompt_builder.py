"""Unit tests for PromptBuilder."""

from app.rag.prompt_builder import PromptBuilder


def test_system_prompt_grounding_rules():
    sys_prompt = PromptBuilder.build_system_prompt()
    assert "NexaRAG" in sys_prompt
    assert "Grounding" in sys_prompt
    assert "[Source 1]" in sys_prompt
    assert "Missing Information" in sys_prompt


def test_system_prompt_custom_instructions():
    custom = "Always format tables using GitHub Markdown."
    sys_prompt = PromptBuilder.build_system_prompt(custom_instructions=custom)
    assert custom in sys_prompt


def test_user_prompt_construction():
    query = "What is the hybrid alpha parameter?"
    context = "[Source 1]\nAlpha parameter controls vector vs BM25 weighting."
    history = [("user", "Hello"), ("assistant", "Hi, how can I help?")]

    prompt = PromptBuilder.build_user_prompt(query=query, context=context, chat_history=history)
    assert "CONVERSATION HISTORY:" in prompt
    assert "DOCUMENT CONTEXT:" in prompt
    assert "USER QUESTION: What is the hybrid alpha parameter?" in prompt
    assert "GROUNDED ANSWER (with [Source X] citations):" in prompt
