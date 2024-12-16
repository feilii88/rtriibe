from typing import Dict, Tuple
from openai import OpenAI
from app.config import constants
import json

class OpenAIClient:
    def __init__(self):
        self.client = OpenAI(api_key=constants.OPENAI_API_KEY)

    def validate_answer(self, question: Dict, answer: str) -> Tuple[bool, str, str]:
        """
        Validate answer using OpenAI
        Returns: (is_valid, normalized_answer, reason)
        """
        if question['id'] == 4 and answer.lower() not in ['yes', 'no']:
            return True, "Valid answer", answer
        
        try:
            # Prepare the prompt based on question type
            if question['type'] == 'boolean':
                prompt = f"""Question: {question['text']}
Answer: {answer}

Analyze if this answer means Yes or No and output 'Yes' or 'No' as the normalized answer. Consider variations and informal responses.
Return exactly in this json format:
{{
    "valid": true,
    "reason": explanation,
    "normalized": normalized_answer
}}"""

            elif question['id'] == 2:  # Days availability
                prompt = f"""Question: {question['text']}
Answer: {answer}

Normalize the answer to a number of days.
Return exactly in this json format:
{{
    "valid": true,
    "reason": explanation,
    "normalized": normalized_answer
}}"""

            elif question['id'] == 3:  # UK location
                prompt = f"""Question: {question['text']}
Answer: {answer}

Analyze if this location is in the UK.
Return exactly in this json format:
{{
    "valid": true,
    "reason": explanation,
    "normalized": normalized_answer
}}"""

            else:
                prompt = f"""Question: {question['text']}
Answer: {answer}

Analyze if this is a valid and clear answer.
Return exactly in this json format:
{{
    "valid": true,
    "reason": explanation,
    "normalized": normalized_answer
}}"""

            # Make OpenAI API call
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a strict answer validator for a job interview."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={ "type": "json_object" }
            )

            # Parse response
            result = response.choices[0].message.content
            print(result)
            is_valid = json.loads(result)['valid']
            reason = json.loads(result)['reason']
            normalized_answer = json.loads(result)['normalized']

            return is_valid, reason, normalized_answer

        except Exception as e:
            print(f"OpenAI validation error: {str(e)}")
            return False, str(answer), "Validation error occurred"

    def should_end_interview(self, question_id: int, normalized_answer: str) -> Tuple[bool, str]:
        """
        Check if interview should be ended based on answer
        Returns: (should_end, end_message)
        """
        if question_id == 1 and normalized_answer.lower() != 'yes':
            return True, "Thank you for your time, but we require UK work eligibility. Goodbye."
            
        elif question_id == 2:
            try:
                days = int(normalized_answer)
                if days < 3:
                    return True, "Thank you for your time, but we require minimum 3 days availability. Goodbye."
            except ValueError:
                return True, "Thank you for your time, but we require clear availability information. Goodbye."
                
        elif question_id == 3:
            if not self._is_uk_location(normalized_answer):
                return True, "Thank you for your time, but we only accept candidates based in the UK. Goodbye."
        
        return False, ""

    def _is_uk_location(self, location: str) -> bool:
        """Check if a location is in the UK using OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a geography expert. Answer with only 'true' or 'false' in json format. For example: {'valid': true/false}"},
                    {"role": "user", "content": f"Is {location} a location in the United Kingdom?"}
                ],
                temperature=0.1,
                response_format={ "type": "json_object" }
            )
            return json.loads(response.choices[0].message.content)['valid']
        except Exception as e:
            print(f"Location check error: {str(e)}")
            return False 