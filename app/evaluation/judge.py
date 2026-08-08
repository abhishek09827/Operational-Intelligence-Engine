from app.core.config import settings
import json
import re
from pydantic import BaseModel
from typing import Optional


class EvaluationResult(BaseModel):
    accuracy_score: int
    completeness_score: int
    actionability_score: int
    reasoning: str


class OpsJudge:
    def __init__(self):
        self.is_openrouter = settings.LLM_PROVIDER.lower() == "openrouter" or (
            settings.OPENROUTER_API_KEY and not settings.GOOGLE_API_KEY
        )
        if self.is_openrouter:
            # OpenRouter reasoning models (e.g. DeepSeek) return extra
            # `reasoning_details` fields that LangChain's ChatOpenAI parser can
            # choke on. We therefore call the raw OpenAI client directly, which
            # matches OpenRouter's documented interface and ignores reasoning.
            self.llm = None
        else:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model_name = settings.GEMINI_MODEL_NAME
            if not model_name.startswith("gemini-") and not model_name.startswith("models/"):
                model_name = "gemini-2.5-flash"
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.0,
            )

    # --- provider completions -------------------------------------------------

    def _openrouter_completion(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
        )
        # DeepSeek-style reasoning models expect the `reasoning` toggle on
        # OpenRouter; if a provider rejects the extra_body param we retry plain.
        try:
            response = client.chat.completions.create(
                model=settings.OPENROUTER_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"reasoning": {"enabled": True}},
            )
        except Exception:
            response = client.chat.completions.create(
                model=settings.OPENROUTER_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
            )

        msg = response.choices[0].message
        content = getattr(msg, "content", None)
        if not content:
            # Reasoning-only responses may place the visible text in reasoning fields.
            content = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None)
        return content or ""

    def _google_completion(self, prompt: str) -> str:
        response = self.llm.invoke(prompt)
        content = response.content
        # LangChain may return content as a list of text blocks; normalize it.
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                else:
                    parts.append(str(block))
            content = "\n".join(parts)
        return content or ""

    def _complete(self, prompt: str) -> str:
        if self.is_openrouter:
            return self._openrouter_completion(prompt)
        return self._google_completion(prompt)

    # --- evaluation -----------------------------------------------------------

    def evaluate_report(self, incident_log: str, generated_report: str, ground_truth: Optional[str] = None) -> EvaluationResult:
        prompt = f"""
        You are a Senior Site Reliability Engineer acting as a judge for an incident report.

        INPUT LOGS:
        {incident_log}

        GENERATED REPORT:
        {generated_report}

        GROUND TRUTH (Optional):
        {ground_truth if ground_truth else "Not provided. Evaluate based on logs."}

        Evaluate the report on the following criteria (1-5 scale):
        1. Accuracy: Does the report correctly identify the error and root cause present in the logs?
        2. Completeness: Does it cover what needs to be fixed and why?
        3. Actionability: Are the fix suggestions concrete and executable?

        Output JSON format:
        {{
            "accuracy_score": <int>,
            "completeness_score": <int>,
            "actionability_score": <int>,
            "reasoning": "<explanation>"
        }}
        """

        content = self._complete(prompt)

        # Clean up code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = None
        error = None
        try:
            data = json.loads(content.strip())
        except Exception as e:
            error = e
            # Reasoning models sometimes prepend explanation text before the JSON.
            match = re.search(r"\{.*?\}", content, re.DOTALL)
            try:
                data = json.loads(match.group(0)) if match else None
            except Exception:
                data = None

        if data is not None:
            try:
                return EvaluationResult(**data)
            except Exception:
                pass

        return EvaluationResult(
            accuracy_score=0,
            completeness_score=0,
            actionability_score=0,
            reasoning=f"Failed to parse evaluation: {error}. Raw content: {content}",
        )

