from contextlib import asynccontextmanager
import os
import uuid
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from azure.identity import DefaultAzureCredential

from dotenv import load_dotenv
load_dotenv(override=True)

import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("azure").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Create a session for the functions to use once, instead of creating a new session for each request
import aiohttp
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    global api_client_session
    api_client_session = aiohttp.ClientSession()
    
    # Regular FastAPI execution
    yield
    
    # Cleanup logic
    await api_client_session.close()
    
app = FastAPI(lifespan=lifespan)

# FastAPI global configuration
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logging.error(f"Unprocessable request: {request} {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

base_url = os.getenv("API_BASE_URL")
async def ask_agents(input_message, conversation_id):
    logger.info(f"Asking agents: {input_message}")
    async with api_client_session.post(f"{base_url}/conversation/{conversation_id}", json={"message": input_message}) as response:
        logger.debug(f"Ask response: {response.status}")
        response.raise_for_status()
        new_messages = await response.json()
        return new_messages

from azure.core.messaging import CloudEvent
from azure.communication.callautomation import (
    PhoneNumberIdentifier,
    RecognizeInputType,
    TextSource,
    SsmlSource
    )

from azure.communication.callautomation.aio import (
    CallAutomationClient
    )
call_automation_client = CallAutomationClient(endpoint=os.getenv("ACS_ENDPOINT"), credential=DefaultAzureCredential())
COGNITIVE_SERVICE_ENDPOINT = os.getenv("COGNITIVE_SERVICE_ENDPOINT")

VOICE_NAME = os.getenv("VOICE_NAME", "en-US-AvaMultilingualNeural")
async def reply_and_wait(replyText, callerId, call_connection_id, context=""):
    try:
        logger.debug("Replying and waiting: %s", replyText)        
        connection_client = call_automation_client.get_call_connection(call_connection_id)
        ssmlToPlay = f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><voice name="{VOICE_NAME}">{replyText}</voice></speak>'
        await connection_client.start_recognizing_media( 
            input_type=RecognizeInputType.SPEECH,
            target_participant=PhoneNumberIdentifier(callerId), 
            end_silence_timeout=1, # The final pause of the speaker used to detect the final result that gets generated as speech.
            play_prompt=SsmlSource(ssml_text=ssmlToPlay) if replyText != "" else None,
            operation_context=context)
    except Exception as ex:
        logger.error("Error in recognize: %s", ex)

async def play_message(call_connection_id, text_to_play, context):
    logger.debug("Playing message: %s", text_to_play)
    play_source = TextSource(text=text_to_play, voice_name=VOICE_NAME) 
    await call_automation_client.get_call_connection(call_connection_id).play_media_to_all(
        play_source,
        operation_context=context)

async def terminate_call(call_connection_id):     
    await call_automation_client.get_call_connection(call_connection_id).hang_up(is_for_everyone=True)  
            
HELLO_PROMPT = "Hello, how may I help you today?"
CHAT_CONTEXT = "ChatContext"
TIMEOUT_SILENCE_PROMPT = "I am sorry, I did not hear anything. If you need assistance, please let me know how I can help you,"
AGENTS_ERROR = "I am sorry, I am unable to assist you at this time. Please try again later."
GOODBYE_PROMPT = "Thank you for calling! I hope I was able to assist you. Have a great day!"
GOODBYE_CONTEXT = "Goodbye"

max_retry_dict = {}
@app.post("/api/call/{contextId}")
async def handle_callback(req: Request):
    try:        
        events = await req.json()
        contextId = req.path_params.get("contextId")
        
        logger.info("Request Json: %s", events)
        for event_dict in events:       
            event = CloudEvent.from_dict(event_dict)
            
            call_connection_id = event.data['callConnectionId']
            logger.info("%s event received for call connection id: %s", event.type, call_connection_id)
            caller_id = req.query_params.get("callerId").strip()
            if "+" not in caller_id:
                caller_id="+".strip()+caller_id.strip()

            logger.info("Call connected: data=%s", event.data)
            if event.type == "Microsoft.Communication.CallConnected":
                max_retry_dict[call_connection_id] = 3
                await reply_and_wait(HELLO_PROMPT, caller_id, call_connection_id, context=CHAT_CONTEXT)
                 
            elif event.type == "Microsoft.Communication.RecognizeCompleted":
                 if event.data['recognitionType'] == "speech": 
                     speech_text = event.data['speechResult']['speech']; 
                     logger.info("Recognition completed, speech_text: %s", speech_text); 
                     if speech_text is not None and len(speech_text) > 0:                      
                          
                        answers = await ask_agents(speech_text, conversation_id=caller_id)
                        # TODO review if and why user resposes are returned in the answers
                        final_answer = "\n".join([answer['content'] for answer in answers if answer['role'] == "assistant"])
                        logger.info("Agent response: %s", final_answer)
                        
                        if final_answer.strip() == "":
                            await reply_and_wait(AGENTS_ERROR, caller_id, call_connection_id, context=CHAT_CONTEXT)
                        else:
                            await reply_and_wait(final_answer, caller_id, call_connection_id, context=CHAT_CONTEXT)
                            # await play_message(call_connection_id, joint_answer, CHAT_CONTEXT)
                            # await reply_and_wait("", caller_id, call_connection_id, context=CHAT_CONTEXT)
                                                 
            elif event.type == "Microsoft.Communication.RecognizeFailed":
                resultInformation = event.data['resultInformation']
                reasonCode = resultInformation['subCode']
                context = event.data['operationContext']
                                
                if reasonCode == 8510 and 0 < max_retry_dict[call_connection_id]:
                    await reply_and_wait(TIMEOUT_SILENCE_PROMPT, caller_id, CHAT_CONTEXT) 
                    max_retry_dict[call_connection_id] -= 1
                else:
                    max_retry_dict.pop(call_connection_id)
                    await play_message(call_connection_id, GOODBYE_PROMPT, GOODBYE_CONTEXT)
                 
            elif event.type == "Microsoft.Communication.PlayCompleted":
                context = event.data['operationContext']    
                if context.lower() == GOODBYE_CONTEXT.lower():
                    await terminate_call(call_connection_id)
                        
        return JSONResponse(status_code=200, content="") 
    except Exception as ex:
        logger.error(f"Error in handle_callback: {ex}")
        return JSONResponse(status_code=500, content=str(ex))
