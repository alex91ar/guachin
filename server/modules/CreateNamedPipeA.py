NAME = "CreateNamedPipe"
DESCRIPTION = "Create a named pipe on the target agent"
PARAMS = [
    {"name":"pipename", "description":"pipe name (e.g. mypipe)", "type":"str"}
]
DEPENDENCIES = []

def CreateNamedPipeA(agent_id, pipename):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr

    agent = Agent.by_id(agent_id)

    # Resolve kernel32!CreateNamedPipeA
    func_addr = Syscall.sys(agent.id, "CreateNamedPipeA")

    scratchpad = agent.scratchpad

    # Prepare pipe name (ANSI)
    pipename_bytes = pipename.encode('ascii') + b'\x00'
    pipename_data, next_ptr = build_ptr(scratchpad, pipename_bytes)
    open_mode = 0x00000003 # PIPE_ACCESS_DUPLEX
    pipe_mode = 0x00000000 # PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT
    max_instances = 255 # PIPE_UNLIMITED_INSTANCES
    out_buffer_size = 0 # Default buffer size
    in_buffer_size = 0 # Default buffer size
    default_timeout = 0 # Default client timeout
    lpSecurityAttributes = 0 # NULL
    # CreateNamedPipeA parameters (x64 ABI)
    params = [
        scratchpad,       # lpName
        open_mode,        # dwOpenMode
        pipe_mode,        # dwPipeMode
        max_instances,    # nMaxInstances
        out_buffer_size,  # nOutBufferSize
        in_buffer_size,   # nInBufferSize
        default_timeout,  # nDefaultTimeOut
        lpSecurityAttributes               # lpSecurityAttributes
    ]

    shellcode = push_rtl(func_addr, params, agent.debug)

    data = pipename_data

    '''
    print
    f"CreateNamedPipeA("
    f"lpName='{hex(scratchpad)}', "
    f"dwOpenMode={hex(open_mode)}, "
    f"dwPipeMode={hex(pipe_mode)}, "
    f"nMaxInstances={max_instances}, "
    f"nOutBufferSize={out_buffer_size}, "
    f"nInBufferSize={in_buffer_size}, "
    f"nDefaultTimeOut={default_timeout}, "
    f"lpSecurityAttributes={hex(lpSecurityAttributes) if lpSecurityAttributes else 0}"
    f")"
    )
    '''
    return data, shellcode


def createNamedPipe(agent_id, pipename):
    from services.orders import write_scratchpad, send_and_wait

    data, shellcode = CreateNamedPipeA(
        agent_id,
        pipename
    )

    write_scratchpad(agent_id, data)

    ret_val = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    #printf"Response from CreateNamedPipe = {hex(ret_val)}")
    return {"retval": ret_val}


def function(agent_id, args):
    #printf"Calling CreateNamedPipeA {args}")
    pipename = args[0]
    result = createNamedPipe(
        agent_id,
        pipename
    )
    return result