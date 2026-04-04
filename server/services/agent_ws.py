import logging
from models.response import Response
from models.module import Module
logger = logging.getLogger(__name__)



def _shell_ws_agent(ws, agent, identity):
    import shlex
    import threading
    import time

    from flask import current_app

    logger.info(f"Starting shell for agent {agent.id} and user {identity}.")

    app = current_app._get_current_object()
    stop_event = threading.Event()


    
    def cmd_help(*args):
        return Module.get_help()

    COMMANDS = {
        "help": cmd_help,
    }

    last_seen_id = -1
    def dispatch_command(text):
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
            module = Module.get(command)
            if module is not None:
                return module.exec(agent.id, args)
            return f"Function {command} not found, use \"help\" to get all available functions."
        else:
            return handler(*args)
    from utils import profile
    def poll_incoming_responses():
        nonlocal last_seen_id

        with app.app_context():
            while not stop_event.is_set():
                try:
                    response_obj = Response.by_agent(agent.id, last_seen_id)
                    if response_obj is None:
                        continue
                    
                    profile(ws.send, response_obj.content)
                    last_seen_id = response_obj.id

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


            with app.app_context():

                # Parse command -> call function -> create request
                request_message = dispatch_command(message)
                if request_message is None:
                    continue
                ws.send(request_message)

    finally:
        stop_event.set()
        try:
            ws.close()
        except Exception:
            pass

        logger.info("Shell %s closed.", agent.id)