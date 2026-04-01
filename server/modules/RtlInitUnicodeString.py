NAME = "RtlInitUnicodeString"
DESCRIPTION = "Initialize a Unicode String"
PARAMS = [
    {"name":"string", "description":"Output buffer address", "type":"hex"},
    {"name":"string", "description":"String to initalize", "type":"str"},
]

def RtlInitUnicodeString(agent_id, buffer_add, string_ptr):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, to_unicode, push_rtl
    agent = Agent.by_id(agent_id)
    call_add = Syscall.sys(agent.id, "RtlInitUnicodeString")
    params = [buffer_add, 
              string_ptr,
             ]
    shellcode = push_rtl(call_add, params, agent.debug)
    print(f"RtlInitUnicodeString(DestinationString={hex(buffer_add)}, SourceString={hex(string_ptr)})")
    return None, shellcode


def InitUS(agent_id, buffer_add, string):
    from services.orders import write_scratchpad, send_and_wait, write_to_agent
    from services.binary import to_unicode
    unicode_str = to_unicode(string)
    write_to_agent(agent_id, buffer_add+16, unicode_str)
    data, shellcode = RtlInitUnicodeString(agent_id, buffer_add, buffer_add+16)
    response_data = int.from_bytes(send_and_wait(agent_id, shellcode), byteorder='little')
    print(f"Response from RtlInitUnicodeString = {hex(response_data)}")
    return response_data

def function(agent_id, args):
    retval = InitUS(agent_id, args[0], args[1])
    return {"OUTLEN":retval, "buffer":args[0]}