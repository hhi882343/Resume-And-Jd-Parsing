from src.ai.prompt import buildTextPrompt, EXTRACTION_PROMPT

def test_prompt_parity():
    text = "John Doe\nSoftware Engineer"
    prompt = buildTextPrompt(text)
    assert prompt.startswith(EXTRACTION_PROMPT)
    assert text in prompt
    assert len(prompt) == len(EXTRACTION_PROMPT) + 2 + 40 + 1 + 6 + 1 + 40 + 1 + len(text)

