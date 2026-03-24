import logging

logger = logging.getLogger(__name__)


def _shell_ws_agent(ws, agent, identity):
    import threading
    import time

    from flask import current_app
    from models import db
    from models.line import Line

    logger.info(f"Starting shell for agent {agent.id} and user {identity}.")

    app = current_app._get_current_object()
    stop_event = threading.Event()

    def poll_incoming():
        last_seen_id = 0

        with app.app_context():
            while not stop_event.is_set():
                try:
                    lines = Line.by_agent_incoming_after(agent.id, last_seen_id)
                    for line in lines:
                        last_seen_id = line.id
                        try:
                            ws.send(line.content)
                        except Exception:
                            stop_event.set()
                            break

                    time.sleep(1)
                except Exception as e:
                    logger.exception("Polling failed for shell %s", agent.id)
                    try:
                        ws.send(f"[error] polling failed: {e}")
                    except Exception:
                        pass
                    stop_event.set()

    poll_thread = threading.Thread(target=poll_incoming, daemon=True)
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
                Line.create_for_agent(
                    agent_id=agent.id,
                    content=text,
                    incoming=False
                )

    finally:
        stop_event.set()
        try:
            ws.close()
        except Exception:
            pass

        logger.info("Shell %s closed.", agent.id)