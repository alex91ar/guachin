import logging
from models.module import Module
from models.agent import Agent
logger = logging.getLogger(__name__)
from models.db import get_session
import shlex
responses = {}
import json


def cmd_help(*args):
    return Module.get_help()

COMMANDS = {
    "help": cmd_help,
}

def dispatch_and_wait(agent, text):
    dispatch_command(agent, text)
    attempts = 10
    while True:
        attempts = attempts -1
        if attempts == 0:
            return None
        if agent.id in responses.keys() and responses[agent.id] is not None:
            print(responses[agent.id])
            response = responses[agent.id]
            del responses[agent.id]
            return response

def _strip_matching_quotes(value):
    if not isinstance(value, str) or len(value) < 2:
        return value

    if (value[0] == value[-1]) and value[0] in ('"', "'"):
        return value[1:-1]

    return value


def dispatch_command(agent, text):
    global responses

    try:
        if isinstance(text, (list, tuple)):
            parts = [str(part) for part in text]
        elif not isinstance(text, str):
            return f"[error] expected command string, got {type(text).__name__}"
        else:
            stripped = text.strip()
            if not stripped:
                return "[error] empty command"

            # Preserve Windows backslashes
            parts = shlex.split(stripped, posix=False)

            # Remove wrapping quotes from each token
            parts = [_strip_matching_quotes(part) for part in parts]

    except ValueError as e:
        print(f"Exception parsing: {e}")
        return f"[error] parse error: {e}"
    except Exception as e:
        print(f"Unexpected parsing exception: {e}")
        return f"[error] unexpected parse error: {e}"

    if not parts:
        return "[error] empty command"

    command = parts[0]
    args = parts[1:]


    handler = COMMANDS.get(command)
    if handler is not None:
        try:
            return handler(*args)
        except Exception as e:
            print(f"Handler exception for '{command}': {e}")
            return f"[error] command failed: {e}"

    try:
        module = Module.by_id(command)
        if module is not None:
            agent.save()
            responses[agent.id] = module.exec(agent.id, args)
            print(f"Got a response!!!!!!: {responses}")
        else:
            responses[agent.id] = Module.get_help()

        agent_obj = Agent.by_id(agent.id)
        if agent_obj is None:
            return None

        return responses.get(agent.id)

    except Exception as e:
        print(f"Module dispatch exception for '{command}': {e}")
        return f"[error] module dispatch failed: {e}"
    
def _shell_ws_agent(ws, agent, identity):
    global responses
    import threading
    import time

    from flask import current_app

    logger.info(f"Starting shell for agent {agent.id} and user {identity}.")

    stop_event = threading.Event()


    from utils import profile
    def poll_incoming_responses():
        while not stop_event.is_set():
            try:
                time.sleep(0.2)
                if agent.id in responses.keys() and responses[agent.id] is not None:
                    print(responses[agent.id])
                    ws.send(responses[agent.id])
                    del responses[agent.id]

            except Exception as e:
                logger.exception("Polling failed for agent %s", agent.id)
                try:
                    ws.send(f"[error] polling failed: {e}")
                except Exception:
                    pass
                stop_event.set()

    poll_thread = threading.Thread(target=poll_incoming_responses, daemon=True)
    poll_thread.start()
    try:
        ws.send(f"[shell] connected to shell {agent.id}")

        while not stop_event.is_set():
            try:
                message = profile(ws.receive)
            except Exception as e:
                logger.info(f"Websocket receive failed or closed for agent {agent.id}: {e}")
                break

            if message is None:
                logger.info("Websocket closed for shell %s", agent.id)
                break



            dispatch_command(agent, message)

    finally:
        stop_event.set()
        try:
            ws.close()
        except Exception:
            pass

        logger.info("Shell %s closed.", agent.id)
        