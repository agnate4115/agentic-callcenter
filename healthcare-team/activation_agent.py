# Assistant Agent - Appointment Scheduler
from pydantic import BaseModel, Field
import os
import logging
from vanilla_aiagents.agent import Agent
from vanilla_aiagents.conversation import LastNMessagesStrategy
from config import llm
from typing import Annotated, Optional
import requests

activation_agent = Agent(
    id="AppointmentScheduler",
    system_message="""You are an appointment scheduler. Your role is to schedule an appointment for the user with the doctor.

You must be accurate and collect all necessary information to schedule the appointment.

Required information:
- Patient's full name
- Patient's email address
- Patient's preferred date and time for the appointment

IMPORTANT NOTES:
- Be polite and professional.
- Confirm the appointment details with the user before finalizing.
- At the end, confirm that the appointment has been scheduled.
""",
    llm=llm,
    description="""Call this Agent if:
- You need to schedule an appointment for the user.
DO NOT CALL THIS AGENT IF:
- You need to greet the user.
- You need to ask the user questions about their condition.
- You need to generate a report.""",
    reading_strategy=LastNMessagesStrategy(10)
)


class PatientData(BaseModel):
    full_name: Annotated[Optional[str], Field(description="The patient's full name")] = None
    email: Annotated[Optional[str], Field(description="The patient's email address")] = None
    preferred_date: Annotated[Optional[str], Field(description="The patient's preferred date for the appointment")] = None
    preferred_time: Annotated[Optional[str], Field(description="The patient's preferred time for the appointment")] = None


class AppointmentData(BaseModel):
    patient: Annotated[PatientData, Field(description="The patient's information")]
    appointment_details: Annotated[str, Field(description="A summary of the appointment details")]


LOGIC_APPS_URL = os.getenv("LOGIC_APPS_URL")
@activation_agent.register_tool(description="Schedule an appointment")
def schedule_appointment(
    payload: Annotated[AppointmentData, "The data required to schedule the appointment"]
    ) -> str:
    logging.info(f"schedule_appointment{payload.model_dump_json(indent=2)}")

    try:
        # Here you would typically interact with a database or an external API to schedule the appointment.
        # For this example, we will just log the appointment details.
        print(f"Appointment scheduled for {payload.patient.full_name} on {payload.patient.preferred_date} at {payload.patient.preferred_time}.")
        return "OK"
    except Exception as e:
        return f"ERROR Failed to schedule appointment: {e}"