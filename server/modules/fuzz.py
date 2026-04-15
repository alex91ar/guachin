NAME = "fuzz"
DESCRIPTION = "Fuzz syscalls"
PARAMS = [
]
DEFAULT = True

def NtCreateNamedPipeFile(agent_id, pipe_name, desired_access, share, create_disposition, oa_attributes):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, build_object_attributes, push_syscall
    import struct
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtCreateNamedPipeFile")
    scratchpad = agent.scratchpad

    # Memory Layout for Syscall
    # 1. FileHandle (8 bytes)
    h_file_data, object_attributes_ptr = build_ptr(scratchpad, b"\x00" * 8)

    # 2. ObjectAttributes (48 bytes)
    object_attributes_data, status_block_ptr = build_object_attributes(object_attributes_ptr, pipe_name, oa_attributes)
    # 3. IoStatusBlock (16 bytes)
    status_block_data, next_ptr = build_ptr(status_block_ptr, b"\x00" * 16)

    params = [
        scratchpad,              # P1:  R10 (&FileHandle)
        desired_access,          # P2:  RDX (Dynamic Access Mask)
        object_attributes_ptr,   # P3:  R8  (&ObjAttr)
        status_block_ptr,        # P4:  R9  (&IoStatusBlock)
        share,                   # P5:  [RSP+0x28] ShareAccess
        create_disposition,      # P6:  [RSP+0x30] CreateDisposition (FILE_CREATE)
        0x20,                    # P7:  [RSP+0x38] CreateOptions (SYNCHRONOUS)
        0x0,                     # P8:  [RSP+0x40] NamedPipeType
        0x0,                     # P9:  [RSP+0x48] ReadMode
        0x0,                     # P10: [RSP+0x50] CompletionMode
        1,      # P11: [RSP+0x58] MaxInstances
        0,                       # P12: [RSP+0x60] InboundQuota
        0,                       # P13: [RSP+0x68] OutboundQuota
        0x0                      # P14: [RSP+0x70] DefaultTimeout
    ]

    shellcode = push_syscall(syscall, params, agent.debug)
    data = h_file_data + object_attributes_data + object_attributes_data + status_block_data
    
    # Trace/Print all parameters for debugging and audit
    #printf"NtCreateNamedPipeFile Parameters:")
    #for i, p in enumerate(params, 1):
        #printf"  P{i:02}: {hex(p) if isinstance(p, int) else p}")
    
    return data, shellcode

def create_params():
    import secrets
    param_count = 10
    params = []
    for i in range(param_count):
        param = secrets.randbits(64)
        params.append(param)
    return params

def function(agent_id, args):
    
    from models.syscall import Syscall
    from services.binary import fuzz_syscall
    from services.orders import send_and_wait
    all = Syscall.all_by_agent(agent_id)
    shellcode = b""
    for syscall in all:
        params = create_params()
        if syscall.syscall < 0xFFFF:
            shellcode += fuzz_syscall(syscall.syscall, params)
    final_syscall = Syscall.sys(agent_id, "NtClose")
    params = create_params()
    shellcode += fuzz_syscall(final_syscall, params,True)
    send_and_wait(agent_id, shellcode)
    return {"retval":0}