import json
import os
import uuid

from app.agent.base import BaseAgent
from app.config import PROJECT_ROOT
from app.flow.flow_factory import FlowFactory, FlowType
from app.flow.planning import PlanningFlow
from app.logger import logger
from app.schema import Message

SESSION_FOLDER = "sessions"


def get_session_id():
    """
    获取session id
    """
    return str(uuid.uuid4())


def get_session_path(session_id: str):
    """
    获取session路径
    """
    session_dir = os.path.join(PROJECT_ROOT, SESSION_FOLDER)
    os.makedirs(session_dir, exist_ok=True)
    return os.path.join(session_dir, session_id + ".json")


def has_session(session_id: str):
    """
    判断session是否存在
    """
    return os.path.exists(get_session_path(session_id))


def load_flow_from_session(
    session_id: str, flow_type: FlowType, agents: dict, planningAgent: BaseAgent
):
    """
    加载session
    """

    flow = FlowFactory.create_flow(
        flow_type=flow_type,
        agents=agents,
        planningAgent=planningAgent,
    )

    try:
        session_path = get_session_path(session_id)
        if os.path.exists(session_path):
            with open(session_path, "r", encoding="utf-8") as f:
                session = json.loads(f.read())

            flow.active_plan_id = session.get("active_plan_id")
            flow.current_step_index = session.get("current_step_index")
            flow.planning_tool.plans = session.get("plans")
            flow.memory.add_messages(
                [
                    Message(
                        role=session_message.get("role"),
                        content=session_message.get("content"),
                        tool_calls=session_message.get("tool_calls"),
                        name=session_message.get("name"),
                        tool_call_id=session_message.get("tool_call_id"),
                        base64_image=session_message.get("base64_image"),
                    )
                    for session_message in session.get("memory", [])
                ]
            )
            for agent_key, agent in flow.agents.items():
                if agent_key in session:
                    session_agent = session[agent_key]
                    agent.current_step = session_agent.get("current_step")
                    agent.state = session_agent.get("state")
                    if flow.memory:
                        agent.memory = flow.memory
                    else:
                        agent.memory.add_messages(
                            [
                                Message(
                                    role=session_message.get("role"),
                                    content=session_message.get("content"),
                                    tool_calls=session_message.get("tool_calls"),
                                    name=session_message.get("name"),
                                    tool_call_id=session_message.get("tool_call_id"),
                                    base64_image=session_message.get("base64_image"),
                                )
                                for session_message in session_agent.get("messages", [])
                            ]
                        )

            if not flow.memory:
                flow.memory = flow.agents[list(flow.agents.keys())[0]].memory

    except Exception as e:
        logger.error(f"load_session error: {str(e)}")

    return flow


def save_flow_to_session(session_id: str, flow: PlanningFlow):
    """
    保存session
    """

    try:
        session = {
            "active_plan_id": flow.active_plan_id,
            "current_step_index": flow.current_step_index,
            "plans": flow.planning_tool.plans,
            "memory": flow.memory.to_dict_list(),
        }
        for agent_key, agent in flow.agents.items():
            session[agent_key] = {
                "current_step": agent.current_step,
                "state": agent.state,
                "messages": agent.memory.to_dict_list(),
            }

        session_path = get_session_path(session_id)
        with open(session_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(session, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"save_session error: {e}")
