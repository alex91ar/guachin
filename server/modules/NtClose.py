NAME = "NtClose"
DESCRIPTION = "Close a handle"
PARAMS = [
    {"name":"file_handle", "description":"Handle of an open file", "type":"hex"}
]

def NtClose(agent_id, handle):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_syscall
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtClose")
    params = [
        handle
             ]
    shellcode = push_syscall(syscall, params)

    print(
        f"NtClose("
        f"Handle={hex(handle)}) "
    )

    return None, shellcode

def closeHandle(agent_id, handle):
    from services.orders import send_and_wait
    data, shellcode = NtClose(agent_id, handle)
    response_data = int.from_bytes(send_and_wait(agent_id, shellcode), byteorder='little')
    print(f"Response from NtClose = {hex(response_data)}")
    return response_data

def function(agent_id, args, dependencies=[]):
    ntstatus = closeHandle(agent_id, args[0])
    return {"NTSTATUS":ntstatus}