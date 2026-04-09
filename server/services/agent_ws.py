import logging
from models.response import Response
from models.module import Module
from models.agent import Agent
logger = logging.getLogger(__name__)
from models.db import get_session
responses = {}

def _shell_ws_agent(ws, agent, identity):
    global responses
    import shlex
    import threading
    import time

    from flask import current_app

    logger.info(f"Starting shell for agent {agent.id} and user {identity}.")

    stop_event = threading.Event()


    
    def cmd_help(*args):
        return Module.get_help()

    COMMANDS = {
        "help": cmd_help,
    }

    def dispatch_command(text):
        global responses
        try:
            parts = shlex.split(text)
        except ValueError as e:
            return f"[error] parse error: {e}"

        if not parts:
            raise Exception

        command = parts[0]
        args = parts[1:]

        handler = COMMANDS.get(command)
        if handler is None:
            print(f"Fetching command from db {command}, args = {args}")
            module = Module.by_id(command)
            if module is not None:
                agent.last_executed = module.id
                agent.save()
                responses[agent.id] = module.exec(agent.id, args)
            else:
                responses[agent.id] = Module.get_help()
            agent_obj = Agent.by_id(agent.id)
            if agent_obj is None:
                return None
        else:
            return handler(*args)
    from utils import profile
    def poll_incoming_responses():
        while not stop_event.is_set():
            try:
                time.sleep(0.2)
                if agent.id in responses.keys() and responses[agent.id] is not None:
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



            dispatch_command(message)

    finally:
        stop_event.set()
        try:
            ws.close()
        except Exception:
            pass

        logger.info("Shell %s closed.", agent.id)