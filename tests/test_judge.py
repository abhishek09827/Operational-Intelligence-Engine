from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.evaluation.judge import OpsJudge


def _google_judge_with(content):
    """An OpsJudge wired to a mocked Google (LangChain) LLM."""
    judge = OpsJudge.__new__(OpsJudge)
    judge.is_openrouter = False
    judge.llm = MagicMock()
    judge.llm.invoke.return_value.content = content
    return judge


def test_evaluate_report_handles_list_content():
    """LangChain/Gemini can return content as a list of blocks; must be parsed."""
    judge = _google_judge_with([
        {"type": "text", "text": '{"accuracy_score": 4, "completeness_score": 5, '
                                 '"actionability_score": 4, "reasoning": "solid"}'}
    ])
    result = judge.evaluate_report("logs", "report", "truth")
    assert result.accuracy_score == 4
    assert result.completeness_score == 5
    assert result.actionability_score == 4
    assert result.reasoning == "solid"


def test_evaluate_report_handles_codeblock_string():
    judge = _google_judge_with('```json\n{"accuracy_score": 3, "completeness_score": 3, '
                               '"actionability_score": 3, "reasoning": "ok"}\n```')
    result = judge.evaluate_report("logs", "report")
    assert result.accuracy_score == 3
    assert result.completeness_score == 3


def test_evaluate_report_returns_zeroes_on_unparseable():
    judge = _google_judge_with("not json at all")
    result = judge.evaluate_report("logs", "report")
    assert (result.accuracy_score, result.completeness_score, result.actionability_score) == (0, 0, 0)


def test_evaluate_report_extracts_json_after_reasoning_text():
    """Reasoning models may prepend prose before the JSON payload."""
    raw = (
        "The report correctly identifies the auth failure. "
        "Here is the score:\n"
        '{"accuracy_score": 3, "completeness_score": 4, "actionability_score": 4, "reasoning": "fine"}'
    )
    judge = _google_judge_with(raw)
    result = judge.evaluate_report("logs", "report")
    assert (result.accuracy_score, result.completeness_score, result.actionability_score) == (3, 4, 4)


def test_openrouter_path_calls_raw_openai_client():
    """The OpenRouter branch must use the OpenAI client with reasoning extra_body."""

    class FakeMsg:
        content = '{"accuracy_score": 5, "completeness_score": 5, "actionability_score": 5, "reasoning": "good"}'

    class FakeChoice:
        message = FakeMsg()

    class FakeResponse:
        choices = [FakeChoice()]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = FakeResponse()

    judge = OpsJudge.__new__(OpsJudge)
    judge.is_openrouter = True

    with patch("openai.OpenAI", return_value=fake_client) as mock_openai:
        result = judge.evaluate_report("logs", "report", "truth")

    assert result.accuracy_score == 5
    mock_openai.assert_called_once_with(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )
    create_kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert create_kwargs["model"] == settings.OPENROUTER_MODEL_NAME
    assert create_kwargs["extra_body"] == {"reasoning": {"enabled": True}}
