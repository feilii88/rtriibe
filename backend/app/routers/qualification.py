from fastapi import APIRouter, HTTPException, Response, Request
from typing import Dict, List
from app.database.candidate import CandidateCRUD, CandidateModel
from app.util.interview_bot import InterviewBot
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateQualification, CandidateInDB
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.twiml.messaging_response import MessagingResponse
from app.util.voice_generator import VoiceGenerator

router = APIRouter(prefix="/qualification", tags=["qualification"])
interview_bot = InterviewBot()
voice_generator = VoiceGenerator()

@router.post("/register", response_model=CandidateResponse)
async def register_candidate(candidate_data: CandidateCreate):
    """Register a new candidate and start qualification process"""
    try:
        # Check if candidate already exists
        existing_candidate = await CandidateCRUD.get_candidate_by_email(candidate_data.email)
        if existing_candidate:
            raise HTTPException(status_code=400, detail="Candidate already registered")

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
    
    if not message or not from_number:
        raise HTTPException(status_code=400, detail="Invalid webhook data")

    # Get bot response
    bot_response = await interview_bot.handle_response(from_number, message)
    
    return {"status": "success", "message": bot_response}

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