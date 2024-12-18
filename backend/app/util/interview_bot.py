from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from typing import Optional, Dict, Any
import json
from app.config import constants
from app.database.candidate import CandidateModel, CandidateCRUD
import asyncio
import requests
from typing import List
from vapi_python import Vapi
from app.util.openai_client import OpenAIClient

class InterviewBot:
    def __init__(self):
        self.twilio_client = Client(constants.TWILIO_ACCOUNT_SID, constants.TWILIO_AUTH_TOKEN)
        self.phone_number = constants.TWILIO_FROM_PHONE  # Regular Twilio number
        self.whatsapp_number = constants.TWILIO_WHATSAPP_NUMBER  # WhatsApp-enabled number
        self.questions = self._load_questions()
        self.total_questions = len(self.questions['questions'])
        # Initialize VAPI
        self.vapi = Vapi(api_key=constants.VAPI_KEY)
        self.openai_client = OpenAIClient()

    def _load_questions(self) -> Dict:
        """Load interview questions from JSON file"""
        with open('app/data/questions.json', 'r') as f:
            return json.load(f)

    async def start_qualification_process(self, candidate: CandidateModel) -> Dict:
        """Start the qualification process with fallback methods"""
        try:
            # Check if the number is a WhatsApp number
            is_whatsapp = await self.check_whatsapp_number(candidate.phone)
            
            # Try WhatsApp methods if available
            if is_whatsapp:
                # Try WhatsApp call
                whatsapp_call_status = await self.try_whatsapp_call(candidate)
                print("WhatsApp call status", str(whatsapp_call_status))
                if whatsapp_call_status.get("success"):
                    candidate.communication_method = "whatsapp_call"
                    await candidate.save()
                    return {"status": "success", "method": "whatsapp_call"}
                
                # If WhatsApp call not answered, try WhatsApp message
                if whatsapp_call_status.get("error") == "no_answer":
                    whatsapp_msg_status = await self.try_whatsapp_message(candidate)
                    print("WhatsApp message status", str(whatsapp_msg_status))
                    if whatsapp_msg_status.get("success"):
                        candidate.communication_method = "whatsapp_message"
                        await candidate.save()
                        return {"status": "success", "method": "whatsapp_message"}

            # Try regular voice call
            voice_call_status = await self.try_voice_call(candidate)
            print("Voice call status", str(voice_call_status))
            if voice_call_status.get("success"):
                candidate.communication_method = "voice_call"
                await candidate.save()
                return {"status": "success", "method": "voice_call"}
            
            # If voice call not answered, try SMS
            if voice_call_status.get("error") == "no_answer":
                sms_status = await self.try_sms(candidate)
                print("SMS status", str(sms_status))
                if sms_status.get("success"):
                    candidate.communication_method = "sms"
                    await candidate.save()
                    return {"status": "success", "method": "sms"}

            # try_sms_status = await self.try_sms(candidate)
            # print("SMS status", str(try_sms_status))
            # if try_sms_status.get("success"):
            #     candidate.communication_method = "sms"
            #     await candidate.save()
            #     return {"status": "success", "method": "sms"}

            return {"status": "failed", "message": "All communication methods failed"}

        except Exception as e:
            print("Qualification process error", str(e))
            return {"status": "error", "message": str(e)}

    async def check_whatsapp_number(self, phone_number: str) -> bool:
        """Check if a phone number is registered with WhatsApp"""
        try:
            # Format the number for WhatsApp
            whatsapp_number = f'whatsapp:{phone_number}'
            
            # Simple status check message
            message = self.twilio_client.messages.create(
                from_=f'whatsapp:{self.whatsapp_number}',
                body='Hi! This is a WhatsApp verification message.',
                to=whatsapp_number
            )
            
            # Wait briefly for status
            await asyncio.sleep(2)
            
            # Fetch the message status
            message = self.twilio_client.messages(message.sid).fetch()
            
            # Consider queued or sent messages as valid WhatsApp numbers
            return message.status in ['queued', 'sent', 'delivered']
            
        except TwilioRestException as e:
            print(f"WhatsApp check error: {str(e)}")
            return False
        except Exception as e:
            print(f"Unexpected error in WhatsApp check: {str(e)}")
            return False

    async def try_voice_call(self, candidate: CandidateModel) -> Dict:
        """Attempt regular voice call with VAPI assistant"""
        try:
            url = "https://api.vapi.ai/call/phone"
            headers = {
                "Authorization": constants.VAPI_KEY,
                "Content-Type": "application/json"
            }

            # Clean the phone number to only keep digits and leading plus sign
            candidatePhone = ''.join(char for char in candidate.phone if char.isdigit() or (char == '+' and candidate.phone.index(char) == 0))

            payload = {
                "phoneNumberId": constants.VAPI_PHONE_NUMBER_ID,
                "customer": {
                    "number": candidatePhone,
                    "name": candidate.name
                },
                "assistant": {
                    "name": "Qualification Assistant",
                    "voice": {
                        "voiceId": constants.VAPI_VOICE_ID,
                        "provider": "11labs",
                        "stability": 0.5,
                        "similarityBoost": 0.75
                    },
                    "model": {
                        "model": "gpt-4o",
                        "messages": [
                            {
                                "role": "system",
                                "content": """You are a qualification interviewer.
Here, pronounce rtribe as /ɑrˈtraɪb/.
First ask: "Hello, I'm calling from rtribe. You have sent your details to us for school based work so I just wanted to run through some initial questions if that's ok?"
If user says no or is not available, say "Thank you for your time. Goodbye." and end the call.

Ask these questions in order (Do not say the question number):
Are you eligible to work in the UK?
   • If No, then say "Thank you for your time, but we require UK work eligibility. Thank you for your interest, goodbye." and end the call
How many days per week are you available to work?
   • If less than 3 weekdays, say "Thank you for your time, but we require minimum 3 days availability. Thank you for your interest, goodbye." and end the call
Where do you currently live? (City or Town please)
   • If the location is unknown, ask "Could you please clarify your location?"
   • If not in the UK, say "Thank you for your time, but we only accept candidates based in the UK. Thank you for your interest, goodbye." and end the call
Have you previously worked in a supply role?
   • If Yes, ask "Which agency did you work with?"
Do you have any restrictions on your availability due to childcare, study, or other commitments?
Do you have a current DBS certificate that is registered on the Update Service?
   • Accept any answer for this question.
-----------------------
After all questions are answered, say "Thank you for that. That's all for now, You should receive a link for your application form if you can complete this as soon as possible we will get you cleared and out working. Many thanks and have a good day." and end the call.
After saying good bye, end the call and don't say anything else.
Be professional but friendly. Listen carefully to answers and ask for clarification if needed."""
                            }
                        ],
                        "provider": "openai",
                        "temperature": 0.7,
                        "maxTokens": 250,
                    },
                    "recordingEnabled": True,
                    "firstMessage": f"Hello {candidate.name}, I'm calling from rtribe. You have sent your details to us for school based work so I just wanted to run through some initial questions if that's ok?",
                    "voicemailMessage": "Sorry we missed you. Please register again when you're available for the interview.",
                    "endCallMessage": "Thank you for that. That's all for now, You should receive a link for your application form if you can complete this as soon as possible we will get you cleared and out working. Many thanks and have a good day.",
                    "transcriber": {
                        "model": "general",
                        "language": "en",
                        "provider": "deepgram"
                    },
                    "server": {
                        "url": f"{constants.BASE_URL}/api/qualification/webhook/vapi"
                    },
                    "clientMessages": [
                        "transcript", "hang", "function-call", "speech-update", 
                        "metadata", "conversation-update"
                    ],
                    "serverMessages": [
                        "end-of-call-report", "status-update", "hang", "function-call", "transcript"
                    ],
                    "endCallPhrases": [
                        "Goodbye.",
                        "Thank you for your time. Goodbye.",
                        "In the future please get in touch with us again. Many thanks for your interest in rTribe. Goodbye."
                    ],
                }
            }

            # Make the call request
            response = requests.post(url, json=payload, headers=headers)
            print("VAPI Response:", response)
            
            if response.status_code == 200:
                return {"success": True}
            else:
                return {"success": False, "error": response.text}
            
        except Exception as e:
            print("Voice call error:", str(e))
            return {"success": False, "error": str(e)}

    async def try_whatsapp_call(self, candidate: CandidateModel) -> Dict:
        """Attempt WhatsApp call"""
        try:
            call = self.twilio_client.calls.create(
                url=f"{constants.BASE_URL}/api/qualification/webhook/voice",
                to=f"whatsapp:{candidate.phone}",  # Format for WhatsApp recipient
                from_=f"whatsapp:{self.whatsapp_number}",  # Use WhatsApp-enabled number
                method='GET'
            )
            
            # Wait for call status (20 seconds timeout)
            await asyncio.sleep(20)
            call = self.twilio_client.calls(call.sid).fetch()
            
            if call.status in ['completed', 'in-progress']:
                return {"success": True}
            else:
                return {"success": False, "error": "no_answer"}
            
        except TwilioRestException as e:
            print(str(e))
            if e.code == 63001:  # WhatsApp number not found
                return {"success": False, "error": "Not a WhatsApp number"}
            return {"success": False, "error": str(e)}

    async def try_whatsapp_message(self, candidate: CandidateModel) -> Dict:
        """Attempt WhatsApp message"""
        try:
            welcome_msg = (
                f"Hi {candidate.name}! Welcome to our recruitment process. "
                "I'll be your interview bot today. "
                "Please reply 'START' when you're ready to begin the interview. "
                "The process will take about 15-20 minutes."
            )
            
            message = self.twilio_client.messages.create(
                from_=f'whatsapp:{self.whatsapp_number}',  # Use WhatsApp-enabled number
                body=welcome_msg,
                to=f'whatsapp:{candidate.phone}'  # Format for WhatsApp recipient
            )
            
            # Wait briefly for message status
            await asyncio.sleep(2)
            message = self.twilio_client.messages(message.sid).fetch()
            
            if message.status in ['sent', 'delivered']:
                return {"success": True}
            return {"success": False, "error": message.status}
            
        except Exception as e:
            print("WhatsApp message error", str(e))
            return {"success": False, "error": str(e)}

    async def try_sms(self, candidate: CandidateModel) -> Dict:
        """Attempt SMS interview"""
        try:
            # Send initial message
            welcome_msg = f"Hi {candidate.name}, I'm from rTriibe. You have sent your details to us for school based work so I just wanted to run through some initial questions if that's ok?"
            
            message = self.twilio_client.messages.create(
                from_=self.phone_number,
                body=welcome_msg,
                to=candidate.phone
            )
            
            if message.sid:
                candidate.communication_method = "sms"
                candidate.current_question = -1  # Special state for waiting for initial confirmation
                await candidate.save()
                return {"success": True}
            
            return {"success": False, "error": "Failed to send SMS"}
            
        except Exception as e:
            print(f"SMS error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def evaluate_availability_answer(self, answer: str) -> bool:
        """Evaluate if candidate meets availability criteria"""
        try:
            answer = answer.lower()
            # Check for direct mentions of 2 or less days
            if any(phrase in answer for phrase in ["2 days", "two days", "1 day", "one day"]):
                return False
                
            # Check for numbers
            import re
            numbers = re.findall(r'\d+', answer)
            if numbers and int(numbers[0]) <= 2:
                return False
                
            return True
        except Exception as e:
            print(f"Error evaluating availability: {str(e)}")
            return True  # Default to true if parsing fails

    async def process_answer(self, candidate: CandidateModel, answer: str) -> str:
        """Process candidate's answer and determine next action"""
        print("Processing answer", answer)
        print("current question", candidate.current_question)
        current_question = self.get_question(candidate.current_question)
        print("current question", current_question)
        if not current_question:
            return "Interview is already completed."

        # Special handling for availability question
        if current_question.get('id') == "availability":
            is_qualified = await self.evaluate_availability_answer(answer)
            if not is_qualified:
                await self.disqualify_candidate(candidate, "Insufficient availability (less than 3 days per week)")
                # Send disqualification message
                disqualification_msg = (
                    "Thank you for your interest. Unfortunately, we require a minimum availability "
                    "of 3 days per week for this position. We cannot proceed with the qualification "
                    "process at this time."
                )
                
                if candidate.communication_method == "whatsapp_message":
                    self.twilio_client.messages.create(
                        from_=f'whatsapp:{self.whatsapp_number}',
                        body=disqualification_msg,
                        to=f'whatsapp:{candidate.phone}'
                    )
                else:
                    self.twilio_client.messages.create(
                        from_=self.phone_number,
                        body=disqualification_msg,
                        to=candidate.phone
                    )
                
                return disqualification_msg

        # Validate answer
        # is_valid, error_msg = self.validate_answer(current_question, answer)
        # if not is_valid:
        #     return error_msg

        # Store answer and increment question counter
        await candidate.store_answer(current_question['id'], answer)
        candidate.current_question += 1
        await candidate.save()

        # Check for follow-up question
        if 'follow_up' in current_question and answer in current_question['follow_up']:
            follow_up = current_question['follow_up'][answer]
            self.twilio_client.messages.create(
                from_=self.phone_number,
                body=follow_up['text'],
                to=candidate.phone
            )
            return "Please answer the follow-up question."

        # Move to next question or conclude
        if candidate.current_question < len(self.questions['questions']):
            await self.send_next_question(candidate)
            return "Answer recorded. Next question sent."
        else:
            await self.conclude_interview(candidate)
            return "Thank you for completing the interview!"

    async def send_next_question(self, candidate: CandidateModel) -> None:
        """Send next question to candidate"""
        question = self.get_question(candidate.current_question)
        print("Question", question)
        
        message = question['text']
        if question['type'] == 'choice':
            options = '\n'.join([f"• {opt}" for opt in question['options']])
            message = f"{message}\n\nOptions:\n{options}"
        
        # Send message based on communication method
        if candidate.communication_method == "whatsapp_message":
            self.twilio_client.messages.create(
                from_=f'whatsapp:{self.phone_number}',
                body=message,
                to=f'whatsapp:{candidate.phone}'
            )
        else:
            self.twilio_client.messages.create(
                from_=self.phone_number,
                body=message,
                to=candidate.phone
            )

    async def conclude_interview(self, candidate: CandidateModel) -> None:
        """Conclude the interview process and evaluate candidate"""
        try:
            # Evaluate candidate using AI
            evaluation_result = await self.evaluate_candidate_with_ai(candidate)
            
            if "error" in evaluation_result:
                # If AI evaluation fails, mark as pending review
                await CandidateCRUD.update_candidate_status(candidate.id, 'pending_review')
                message = (
                    "Thank you for completing the interview! "
                    "Our team will review your answers and get back to you soon."
                )
            else:
                # Update candidate status based on AI evaluation
                new_status = 'qualified' if evaluation_result['qualified'] else 'disqualified'
                await CandidateCRUD.update_candidate_status(
                    candidate.id, 
                    new_status,
                    disqualification_reason=None if evaluation_result['qualified'] else "Did not meet qualification criteria"
                )
                
                # Store evaluation scores
                await candidate.store_evaluation_scores(evaluation_result['scores'])
                
                # Prepare appropriate message
                if evaluation_result['qualified']:
                    message = (
                        "Congratulations! You have successfully completed the qualification process. "
                        "Our team will contact you shortly with next steps."
                    )
                else:
                    message = (
                        "Thank you for your interest. After careful evaluation, we regret to inform you "
                        "that we cannot proceed with your application at this time."
                    )
            
            # Send conclusion message
            if candidate.communication_method == "whatsapp_message":
                self.twilio_client.messages.create(
                    from_=f'whatsapp:{self.whatsapp_number}',
                    body=message,
                    to=f'whatsapp:{candidate.phone}'
                )
            else:
                self.twilio_client.messages.create(
                    from_=self.phone_number,
                    body=message,
                    to=candidate.phone
                )
                
        except Exception as e:
            print(f"Error in conclude_interview: {str(e)}")
            # Handle error gracefully
            await CandidateCRUD.update_candidate_status(candidate.id, 'error')

    def validate_answer(self, question: Dict[str, Any], answer: str) -> tuple[bool, Optional[str]]:
        """Validate answer based on question type"""
        if question['type'] == 'boolean':
            if answer.lower() not in ['yes', 'no']:
                return False, "Please answer with Yes or No"
        elif question['type'] == 'number':
            try:
                float(answer)
            except ValueError:
                return False, "Please provide a valid number"
        elif question['type'] == 'choice':
            if answer not in question['options']:
                return False, f"Please choose from: {', '.join(question['options'])}"
        
        return True, None

    async def disqualify_candidate(self, candidate: CandidateModel, reason: str) -> None:
        """Mark candidate as disqualified"""
        candidate.status = "disqualified"
        candidate.disqualification_reason = reason
        await candidate.save()

    async def send_welcome_message(self, candidate: CandidateModel) -> None:
        """Send initial welcome message with instructions"""
        welcome_msg = (
            f"Hi {candidate.name}! Welcome to our recruitment process. "
            "I'll be your interview bot today. "
            "Please reply 'START' when you're ready to begin the interview. "
            "The process will take about 15-20 minutes."
        )
        
        self.twilio_client.messages.create(
            from_=self.phone_number,
            body=welcome_msg,
            to=candidate.phone
        )

    async def handle_response(self, from_number: str, message: str) -> str:
        """Handle incoming SMS responses"""
        try:
            # Get candidate
            candidate = await CandidateCRUD.get_candidate_by_phone(from_number)
            if not candidate:
                return "Sorry, we couldn't find your registration. Please register first."

            # Handle initial confirmation
            if candidate.current_question == -1:
                if any(word.lower() in message.lower() for word in ['yes', 'yeah', 'sure', 'ok', 'okay', 'yep', 'yup', 'y', 'ye']):
                    candidate.current_question = 0
                    await candidate.save()
                    # Send first question
                    return self.questions['questions'][0]['text']
                else:
                    return "Thank you for your time. Goodbye."

            # Get current question
            if candidate.current_question >= len(self.questions['questions']):
                return "Interview already completed. Thank you!"

            current_question = self.questions['questions'][candidate.current_question]

            # Validate answer using OpenAI
            is_valid, reason, normalized_answer = self.openai_client.validate_answer(current_question, message)
            
            if not is_valid:
                return f"I didn't quite understand that. {reason}"

            # Check if interview should end based on answer
            should_end, end_message = self.openai_client.should_end_interview(
                current_question['id'], 
                normalized_answer
            )
            
            if should_end:
                candidate.status = "disqualified"
                candidate.disqualification_reason = end_message
                await candidate.save()
                return end_message

            # Store the answer
            await candidate.store_answer(current_question['id'], normalized_answer)

            # Handle follow-up question for supply role
            if current_question['id'] == 4 and message.lower() == 'yes':
                return "Which agency did you work with?"

            # Move to next question
            candidate.current_question += 1
            await candidate.save()

            # Check if interview is complete
            if candidate.current_question >= len(self.questions['questions']):
                candidate.status = "pending"
                await candidate.save()
                return ("Thank you for that. That's all for now, You should receive a link for your application form "
                       "if you can complete this as soon as possible we will get you cleared and out working. "
                       "Many thanks and have a good day.")

            # Send next question
            return self.questions['questions'][candidate.current_question]['text']

        except Exception as e:
            print(f"Error handling SMS response: {str(e)}")
            return "Sorry, there was an error processing your response. Please try again."

    def get_question(self, question_number: int, previous_answer: Optional[str] = None) -> Dict[str, Any]:
        """Get question by number, considering follow-ups"""
        if question_number >= len(self.questions['questions']):
            return None

        question = self.questions['questions'][question_number]
        
        # If there's a previous answer and current question has follow-ups
        if previous_answer and 'follow_up' in question and previous_answer in question['follow_up']:
            return {
                'id': f"{question['id']}_followup",
                **question['follow_up'][previous_answer]
            }
        
        return question

    async def evaluate_candidate_with_ai(self, candidate: CandidateModel) -> Dict[str, Any]:
        """Evaluate candidate's answers using Relevance AI API"""
        try:
            # Get all answers in a structured format
            answers = json.loads(candidate.answers)
            
            # Prepare the evaluation prompt
            prompt = self._prepare_evaluation_prompt(answers)
            
            # Call Relevance AI API
            headers = {
                "Authorization": f"{constants.RELEVANCE_AI_PROJECT}:{constants.RELEVANCE_AI_API_KEY}"
            }
            
            payload = {
                "prompt": prompt,
                "criteria": {
                    "experience": "Evaluate candidate's experience with children and in schools (score 0-1)",
                    "availability": "Check if availability meets requirements - minimum 3 days/week (score 0-1)",
                    "location": "Assess location and travel capabilities (score 0-1)",
                    "motivation": "Evaluate motivation and commitment to working in schools (score 0-1)"
                }
            }
            
            response = requests.post(
                f'https://api-{constants.RELEVANCE_AI_REGION}.stack.tryrelevance.com/latest/evaluate',
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise Exception(f"Relevance AI API error: {response.text}")
            
            evaluation = response.json().get("evaluation", {})
            overall_score = sum(evaluation.values()) / len(evaluation)
            
            return {
                "qualified": overall_score >= 0.7,  # 70% threshold
                "scores": evaluation,
                "overall_score": overall_score
            }
            
        except Exception as e:
            print(f"AI evaluation error: {str(e)}")
            return {"error": str(e)}

    def _prepare_evaluation_prompt(self, answers: List[Dict]) -> str:
        """Prepare evaluation prompt from candidate's answers"""
        prompt = (
            "Please evaluate this teaching assistant candidate based on their interview answers. "
            "Score each criterion from 0 to 1, where 1 is excellent and 0 is poor.\n\n"
        )
        
        for answer in answers:
            question = next((q for q in self.questions['questions'] if q['id'] == answer['question']), None)
            if question:
                prompt += f"Question: {question['text']}\nAnswer: {answer['answer']}\n\n"
        
        return prompt

    async def start_interview(self, candidate: CandidateModel) -> None:
        """Start the interview process"""
        # Reset question counter and update status
        candidate.current_question = 0  # Make sure we start from the first question
        candidate.status = "in_progress"
        await candidate.save()

        # Send first question
        await self.send_next_question(candidate)