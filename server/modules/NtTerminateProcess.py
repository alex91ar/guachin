NAME = "NtTerminateProcess"
DESCRIPTION = "Directly terminates a process and all of its threads via native syscall."
PARAMS = [
    {"name": "h_process", "description": "Handle to the process to terminate", "type": "hex"},
    {"name": "exit_status", "description": "The exit code to set for the process", "type": "hex", "optional": True, "default": "0x0"}
]
DEPENDENCIES = []
DEFAULT = True

def NtTerminateProcess_Payload(agent_id, h_process, exit_status):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall_id = Syscall.sys(agent.id, "NtTerminateProcess")
    
    # Syscall Signature:
    # NTSTATUS NtTerminateProcess(
    #   HANDLE   ProcessHandle,
    #   NTSTATUS ExitStatus
    # );
    
    params = [
        h_process,   # RCX: Handle to target process
        exit_status  # RDX: Desired exit code
    ]
    
    # This syscall does not require scratchpad structures, parameters are passed in registers.
    return b"", push_syscall(syscall_id, params, agent.debug)

def function(agent_id, args):
    from services.orders import send_and_wait
    import struct

    # 1. Parse Arguments
    h_process = args[0]
    exit_status = args[1]

    # 2. Generate and Execute Shellcode
    # No data needs to be written to the scratchpad for this specific syscall.
    data, shellcode = NtTerminateProcess_Payload(agent_id, h_process, exit_status)
    
    # Execute the syscall
    response_bytes = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response_bytes, 'little')

    return {
        "retval": hex(ntstatus),
        "params": {
            "h_process": hex(h_process),
            "exit_status": hex(exit_status)
        }
    }