NAME = "CreateFile"
DESCRIPTION = "Create or open a file on the target agent"
PARAMS = [
    {"name":"filename", "description":"Path to file", "type":"str"},
    {"name":"desired_access", "description":"Access flags (e.g. GENERIC_READ)", "type":"hex"},
]
DEPENDENCIES = []
DEFAULT = True

def CreateFileA(agent_id, filename, desired_access):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr

    agent = Agent.by_id(agent_id)

    # Resolve kernel32!CreateFileA
    func_addr = Syscall.sys(agent.id, "CreateFileA")

    scratchpad = agent.scratchpad

    # Prepare filename (ANSI)
    filename_bytes = filename.encode('ascii') + b'\x00'
    filename_data, next_ptr = build_ptr(scratchpad, filename_bytes)

    # CreateFileA parameters (x64 ABI)
    params = [
        scratchpad,     # lpFileName
        desired_access,   # dwDesiredAccess (NOW PARAMETERIZED)
        0,                # dwShareMode
        0,                # lpSecurityAttributes
        4,                # dwCreationDisposition (CREATE_ALWAYS)
        0x80,             # dwFlagsAndAttributes (FILE_ATTRIBUTE_NORMAL)
        0                 # hTemplateFile
    ]

    shellcode = push_rtl(func_addr, params, agent.debug)

    data = filename_data

    #printf"CreateFileA(File='{filename}', Access={hex(desired_access)}, pFile={hex(scratchpad)})")
    return data, shellcode


def createFile(agent_id, filename, desired_access):
    from services.orders import write_scratchpad, send_and_wait

    data, shellcode = CreateFileA(agent_id, filename, desired_access)

    write_scratchpad(agent_id, data)

    ret_val = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')

    return {"retval": hex(ret_val)}


def function(agent_id, args):
    filename = args[0]
    desired_access = args[1]

    result = createFile(agent_id, filename, desired_access)
    return result