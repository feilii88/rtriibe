from fastapi import APIRouter, HTTPException, Response, Request
from typing import Dict, List
from app.database.candidate import CandidateCRUD, CandidateModel
from app.util.interview_bot import InterviewBot
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateQualification, CandidateInDB
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.twiml.messaging_response import MessagingResponse
from app.util.voice_generator import VoiceGenerator
import json
from datetime import datetime

router = APIRouter(prefix="/qualification", tags=["qualification"])
interview_bot = InterviewBot()
voice_generator = VoiceGenerator()

@router.post("/register", response_model=CandidateResponse)
async def register_candidate(candidate_data: CandidateCreate):
    """Register a new candidate and start qualification process"""
    try:
        # Check if candidate already exists by email
        existing_candidate = await CandidateCRUD.get_candidate_by_email(candidate_data.email)
        if existing_candidate:
            raise HTTPException(status_code=400, detail="Candidate already registered with this email")

        # Check if candidate already exists by phone number
        existing_candidate = await CandidateCRUD.get_candidate_by_phone(candidate_data.phone)
        if existing_candidate:
            raise HTTPException(status_code=400, detail="Candidate already registered with this phone number")

        print("Creating candidate")
        # Create candidate
        candidate = await CandidateCRUD.create_candidate(candidate_data.dict())

        # Start qualification process with fallback methods
        print("Starting qualification process")
        qualification_status = await interview_bot.start_qualification_process(candidate)
        
        if qualification_status["status"] == "success":
            return CandidateResponse(
                status="success",
                message=f"Registration successful. We'll contact you via {qualification_status['method']}",
                data=CandidateInDB.from_orm(candidate)
            )
        else:
            return CandidateResponse(
                status="error",
                message="Registration successful but couldn't initiate contact. We will try again shortly.",
                data=CandidateInDB.from_orm(candidate)
            )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/webhook/voice")
async def voice_webhook(request: Request):
    """Handle incoming voice calls"""
    params = request.query_params
    response = VoiceResponse()
    
    from_number = params.get('To', '').strip()
    candidate = await CandidateCRUD.get_candidate_by_phone(from_number)
    
    if not candidate:
        # Generate voice URL for error message
        voice_url = await voice_generator.generate_speech(
            "Sorry, we couldn't find your registration. Please register first."
        )
        if voice_url:
            response.play(voice_url)
        else:
            response.say("Sorry, we couldn't find your registration. Please register first.")
        return Response(content=str(response), media_type="application/xml")

    # Handle different stages of the voice interview
    if candidate.current_question == 0:
        welcome_text = "Welcome to the qualification interview. Press 1 to begin."
        voice_url = await voice_generator.generate_speech(welcome_text)
        print(f"Voice URL: {voice_url}")
        
        gather = Gather(
            input='dtmf',
            num_digits=1, 
            action="/api/qualification/webhook/voice/response",
            method='GET',
            timeout=10
        )
        
        if voice_url:
            gather.play(voice_url)
        else:
            gather.say(welcome_text)
        response.append(gather)
    else:
        # Continue with current question
        question = interview_bot.get_question(candidate.current_question)
        voice_url = await voice_generator.generate_speech(question['text'])
        
        gather = Gather(
            input='speech',
            action="/api/qualification/webhook/voice/response",
            method='GET',
            timeout=3,
            language='en-GB'
        )
        
        if voice_url:
            gather.play(voice_url)
        else:
            gather.say(question['text'])
        response.append(gather)
        
        response.redirect("/api/qualification/webhook/voice", method='GET')

    return Response(content=str(response), media_type="application/xml")

@router.get("/webhook/voice/response")
async def voice_response_webhook(request: Request):
    """Handle voice responses"""
    params = request.query_params
    response = VoiceResponse()
    from_number = params.get('To', '').strip()
    speech_result = params.get('SpeechResult')
    digits = params.get('Digits')

    print("Speech result:", speech_result)
    
    candidate = await CandidateCRUD.get_candidate_by_phone(from_number)
    
    if not candidate:
        voice_url = await voice_generator.generate_speech("Session expired. Please try again.")
        if voice_url:
            response.play(voice_url)
        else:
            response.say("Session expired. Please try again.")
        return Response(content=str(response), media_type="application/xml")

    # Handle initial "Press 1" response
    if candidate.current_question == 0 and digits == '1':
        question = interview_bot.get_question(0)
        voice_url = await voice_generator.generate_speech(question['text'])
        
        gather = Gather(
            input='speech',
            action="/api/qualification/webhook/voice/response",
            method='GET',
            timeout=3,
            language='en-GB'
        )
        
        if voice_url:
            gather.play(voice_url)
        else:
            gather.say(question['text'])
            
        response.append(gather)
        response.redirect("/api/qualification/webhook/voice", method='GET')
        return Response(content=str(response), media_type="application/xml")

    if speech_result:
        # Store answer first
        await candidate.store_answer(candidate.current_question, speech_result)
        candidate.current_question += 1
        await candidate.save()
        
        if candidate.current_question < interview_bot.total_questions:
            # Get next question text
            question = interview_bot.get_question(candidate.current_question)
            
            # Generate voice in background while preparing response
            voice_url = await voice_generator.generate_speech(question['text'])
            
            gather = Gather(
                input='speech',
                action="/api/qualification/webhook/voice/response",
                method='GET',
                timeout=3,  # Reduced timeout
                language='en-GB'
            )
            
            if voice_url:
                gather.play(voice_url)
            else:
                gather.say(question['text'])
                
            response.append(gather)
            response.redirect("/api/qualification/webhook/voice", method='GET')
        else:
            completion_msg = "Thank you for completing the interview. We will review your answers and get back to you soon."
            voice_url = await voice_generator.generate_speech(completion_msg)
            
            if voice_url:
                response.play(voice_url)
            else:
                response.say(completion_msg)
                
            await interview_bot.conclude_interview(candidate)
    else:
        question = interview_bot.get_question(candidate.current_question)
        error_msg = "I didn't catch that. " + question['text']
        voice_url = await voice_generator.generate_speech(error_msg)
        
        gather = Gather(
            input='speech',
            action="/api/qualification/webhook/voice/response",
            method='GET',
            timeout=3,
            speechTimeout=2,
            language='en-GB'
        )
        
        if voice_url:
            gather.play(voice_url)
        else:
            gather.say(error_msg)
            
        response.append(gather)
        response.redirect("/api/qualification/webhook/voice", method='GET')

    return Response(content=str(response), media_type="application/xml")

@router.post("/webhook/sms")
async def sms_webhook(request: Request):
    """Handle incoming SMS messages"""
    data = await request.form()
    message = data.get('Body')
    from_number = data.get('From').strip()

    print("Message:", message)
    print("From number:", from_number)
    
    if not message or not from_number:
        raise HTTPException(status_code=400, detail="Invalid webhook data")

    # Get bot response
    print("Getting bot response")
    bot_response = await interview_bot.handle_response(from_number, message)
    print("Bot response:", bot_response)
    
    resp = MessagingResponse()
    resp.message(bot_response)
    
    # Return TwiML response
    return Response(content=str(resp), media_type="application/xml")

@router.get("/status/{candidate_id}", response_model=CandidateQualification)
async def get_qualification_status(candidate_id: int):
    """Get candidate's qualification status"""
    candidate = await CandidateCRUD.get_by_id(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    return {
        "status": candidate.status,
        "completed_questions": candidate.current_question,
        "total_questions": interview_bot.total_questions,
        "qualified": candidate.status == "qualified"
    } 

@router.post("/webhook/vapi")
async def vapi_webhook(request: Request):
    """Handle VAPI webhooks for call updates"""
    data = await request.json()
    print("VAPI Webhook Data:", data)
    try:
        # Get the customer phone number from the message data structure
        message_data = data.get('message', {})
        
        # Get customer info from the call object if it exists
        call_data = message_data.get('call', {})
        customer_data = call_data.get('customer', {}) or message_data.get('customer', {})
        customer_number = customer_data.get('number')
        
        if not customer_number:
            return {"status": "error", "message": "No customer number provided"}
        print("Customer number:", customer_number)

        # Get the candidate
        candidate = await CandidateCRUD.get_candidate_by_phone(customer_number)
        if not candidate:
            return {"status": "error", "message": "Candidate not found"}
        print("Candidate:", candidate)

        # Handle status updates
        if message_data.get('type') == 'status-update':
            status = message_data.get('status')
            ended_reason = message_data.get('endedReason')
            print("Status, ended reason:", status, ended_reason)
            
            # If call was declined/busy/no-answer, try SMS
            if status == 'ended' and ended_reason in ['customer-busy', 'no-answer', 'declined', 'voicemail', 'customer-did-not-answer', 'assistant-said-end-call-phrase']:
                print(f"Call ended with reason: {ended_reason}. Trying SMS...")
                sms_status = await interview_bot.try_sms(candidate)
                if sms_status.get("success"):
                    candidate.communication_method = "sms"
                    await candidate.save()
                    print("Successfully switched to SMS")
                else:
                    print("SMS fallback failed:", sms_status.get("error"))

        # Handle end-of-call report
        elif message_data.get('type') == 'end-of-call-report':
            # Get transcript directly from message_data
            transcript = message_data.get('artifact', {}).get('messages', [])
            if transcript:
                try:
                    # Parse current answers
                    try:
                        current_answers = json.loads(candidate.answers)
                    except (json.JSONDecodeError, TypeError):
                        current_answers = []
                    
                    # Add full transcript
                    current_answers.extend(transcript)
                    
                    # Update candidate's answers
                    candidate.answers = json.dumps(current_answers)
                    candidate.status = "pending"
                    await candidate.save()
                    
                except Exception as e:
                    print(f"Error saving transcript: {str(e)}")

        return {"status": "success"}

    except Exception as e:
        print(f"Error processing VAPI webhook: {str(e)}")
        return {"status": "error", "message": str(e)}