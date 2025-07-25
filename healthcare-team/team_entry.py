from typing import Dict, List, Tuple
from vanilla_aiagents.team import Team
from user_proxy_agent import user_proxy_agent
from therapist_agent import therapist_agent
from activation_agent import activation_agent
from planner_agent import planner_agent
from report_agent import report_agent
from config import llm

system_message_manager="""
    You are the overall manager of the group chat. 
    You can see all the messages and intervene if necessary. 
    You can also send system messages to the group chat. 
    
    If you need human or user input, you can ask Customer for more information.
    NEVER call Customer immediately after Executor
    """
team = Team(
    id="healthcare-team",
    description="A group chat with multiple agents for healthcare",
    members=[user_proxy_agent, planner_agent, therapist_agent, activation_agent, report_agent],
    llm=llm, 
    stop_callback=lambda msgs: "terminate" in msgs[-1].get("content", "").lower(),
)
