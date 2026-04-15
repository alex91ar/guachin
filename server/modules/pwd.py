NAME = "pwd"
DESCRIPTION = "Gets the current directory."
PARAMS = [
]

DEPENDENCIES = [
    "NtQueryInformationProcess",
]

def get_current_directory(agent_id):
    """Helper to read the current directory from the PEB -> ProcessParameters."""
    from services.orders import send_and_wait, read_scratchpad, read_from_agent
    from models.syscall import Syscall
    from models.agent import Agent
    import struct

    agent = Agent.by_id(agent_id)
    # 1. Get PEB via NtQueryInformationProcess
    syscall = Syscall.sys(agent.id, "NtQueryInformationProcess")
    params = [0xFFFFFFFFFFFFFFFF, 0, agent.scratchpad, 48, 0] 
    from services.binary import push_syscall
    shellcode = push_syscall(syscall, params, agent.debug)
    send_and_wait(agent_id, shellcode)
    
    struct_data = read_scratchpad(agent_id, 48)
    peb_addr = struct.unpack_from("<Q", struct_data, 8)[0]

    # 2. PEB + 0x20 -> ProcessParameters
    proc_params_ptr_raw = read_from_agent(agent_id, peb_addr + 0x20, 8)[:8]
    #printproc_params_ptr_raw)
    proc_params_addr = struct.unpack("<Q", proc_params_ptr_raw)[0]

    # 3. ProcessParameters + 0x38 -> CurrentDirectory (UNICODE_STRING)
    # UNICODE_STRING: [Length(2)][MaxLength(2)][Pad(4)][BufferPtr(8)]
    cur_dir_struct = read_from_agent(agent_id, proc_params_addr + 0x38, 16)
    length = struct.unpack("<H", cur_dir_struct[0:2])[0]
    buffer_ptr = struct.unpack("<Q", cur_dir_struct[8:16])[0]

    # 4. Read the actual string
    raw_name = read_from_agent(agent_id, buffer_ptr, length)
    return raw_name.decode("utf-16le", errors="ignore")

def function(agent_id, args):
    return {"retval":0, "pwd":get_current_directory(agent_id)}