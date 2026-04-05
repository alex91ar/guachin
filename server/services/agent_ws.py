import logging
from models.response import Response
from models.module import Module
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
            print(f"Fetching command from db {command}")
            module = Module.by_id(command)
            if module is not None:
                responses[agent.id] = module.exec(agent.id, args)
            return f"Function {command} not found, use \"help\" to get all available functions."
        else:
            return handler(*args)
    from utils import profile
    def poll_incoming_responses():

        while not stop_event.is_set():
            try:
                time.sleep(0.1)
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