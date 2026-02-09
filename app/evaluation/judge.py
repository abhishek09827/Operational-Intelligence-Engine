from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings
import json
from pydantic import BaseModel
from typing import Optional

class EvaluationResult(BaseModel):
    accuracy_score: int
    completeness_score: int
    actionability_score: int
    reasoning: str

class OpsJudge:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.0
        )

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
        
        response = self.llm.invoke(prompt)
        content = response.content
        
        # Clean up code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        try:
            data = json.loads(content.strip())
            return EvaluationResult(**data)
        except Exception as e:
            return EvaluationResult(
                accuracy_score=0, 
                completeness_score=0, 
                actionability_score=0, 
                reasoning=f"Failed to parse evaluation: {e}. Raw content: {content}"
            )
