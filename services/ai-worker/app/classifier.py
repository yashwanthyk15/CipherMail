import google.generativeai as genai
import json
import logging
import time
from .config import settings

logger = logging.getLogger(__name__)

class AIClassifier:
    def __init__(self, api_key: str):
        self.api_key = api_key
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            self.model = None
            logger.warning("No Gemini API key provided. Running in mock mode.")
        self.consecutive_failures = 0
        self.circuit_open_until = 0

    def _get_mock_result(self, email_data: dict, reason_prefix: str) -> dict:
        sender = email_data.get('sender_email', '').lower()
        if 'paypal' in sender or 'security' in sender or 'update' in sender:
            return {
                "phishing_risk": 95,
                "reason": f"{reason_prefix}: High risk keywords found in sender domain",
                "indicators": ["Suspicious sender domain", "Urgent language detected"]
            }
        return {
            "phishing_risk": 15,
            "reason": f"{reason_prefix}: No obvious threats detected",
            "indicators": []
        }

    async def classify(self, email_data: dict) -> dict:
        if not self.model:
            return self._get_mock_result(email_data, "Mock mode")

        if time.time() < self.circuit_open_until:
            logger.warning("Circuit breaker is open. Skipping Gemini API call.")
            return self._get_mock_result(email_data, "Circuit breaker")

        prompt = f"""
        Analyze this email for phishing risk.
        Sender: {email_data.get('sender_email')}
        Subject: {email_data.get('subject')}
        Body (first 500 chars): {email_data.get('body_excerpt')}
        Suspicious URLs found: {[u.get('url') for u in email_data.get('urls', [])]}
        
        Classify as JSON:
        {{
            "phishing_risk": (0-100 numeric score),
            "reason": "brief explanation",
            "indicators": ["list of suspicious patterns"]
        }}
        """
        
        try:
            # Using generate_content async version if available, or wrapping sync
            import asyncio
            loop = asyncio.get_event_loop()
            
            # Setting response_mime_type to application/json is supported in recent gemini SDKs
            response = await loop.run_in_executor(
                None, 
                lambda: self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.2
                    )
                )
            )
            
            result_json = response.text.strip()
            if result_json.startswith('```json'):
                result_json = result_json[7:]
            if result_json.startswith('```'):
                result_json = result_json[3:]
            if result_json.endswith('```'):
                result_json = result_json[:-3]
            self.consecutive_failures = 0
            return json.loads(result_json.strip())
        except Exception as e:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.circuit_open_until = time.time() + 60
                logger.error(f"Circuit breaker tripped due to 3 consecutive failures. Pausing for 60s.")
            
            logger.error(f"Error calling Gemini API: {e}")
            
            # Re-raise so the DLQ logic in main.py can catch it
            raise
