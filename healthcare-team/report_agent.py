from vanilla_aiagents.agent import Agent
from vanilla_aiagents.conversation import LastNMessagesStrategy
from config import llm
from typing import Annotated
from azure.core.credentials import AzureKeyCredential
import os

report_agent = Agent(
    id="ReportGenerator",
    system_message="""You are a report generator. Your role is to generate a comprehensive report based on the conversation between the user and the therapist agent.

Your tasks are:
- Summarize the conversation in a clear and concise way.
- The report should include the user's main concerns, the questions asked by the therapist agent, and the user's responses.
- The report should be structured in a way that is easy for the doctor to read and understand.
- The report should also be shared with the user.

IMPORTANT NOTES:
- Be objective and accurate in your reporting.
- Do not include any personally identifiable information in the report.
""",
    llm=llm,
    description="""Call this Agent if:
- You need to generate a report of the conversation.
DO NOT CALL THIS AGENT IF:
- You need to greet the user.
- You need to ask the user questions about their condition.
- You need to schedule an appointment.""",
    reading_strategy=LastNMessagesStrategy(10)
)

@report_agent.register_tool(description="Generate a report of the conversation")
def generate_report(
    conversation_summary: Annotated[str, "A summary of the conversation between the user and the therapist agent."]
    ) -> Annotated[str, "A comprehensive report of the conversation."]:

    # Here you would typically format the report and send it to the doctor and the user.
    # For this example, we will just print the report to the console.
    print("--- Conversation Report ---")
    print(conversation_summary)
    print("-------------------------")

    return "Report generated successfully."