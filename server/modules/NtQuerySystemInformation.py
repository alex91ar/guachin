NAME = "NtQuerySystemInformation"
DESCRIPTION = "Retrieve global system information (Process list, Handle table, Module list) via native syscall"
PARAMS = [
    {"name":"info_class", "description":"SystemInformationClass (5 for SystemProcessInformation)", "type":"int"}
]
DEFAULT = True

def NtQuerySystemInformation_Shellcode(agent_id, info_class):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall_id = Syscall.sys(agent_id, "NtQuerySystemInformation")
    scratchpad = agent.scratchpad
    
    # 1. Prepare buffer in scratchpad to receive the system data
    # SystemProcessInformation often requires 64KB+ for full enumeration
    
    # Syscall Parameters (NTDLL Standard):
    # 1. SYSTEM_INFORMATION_CLASS SystemInformationClass
    # 2. PVOID SystemInformation (Pointer to our buffer in scratchpad)
    # 3. ULONG SystemInformationLength
    # 4. PULONG ReturnLength (Optional NULL = 0)
    
    params = [
        info_class,          # SystemInformationClass
        scratchpad,          # &SystemInformation
        0x100000,         # SystemInformationLength
        0                    # ReturnLength (NULL)
    ]
    
    shellcode = push_syscall(syscall_id, params, agent.debug)
    return shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, read_scratchpad

    info_class = args[0]
    shellcode = NtQuerySystemInformation_Shellcode(agent_id, info_class)
    
    # 2. Trigger the syscall execution
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    # 3. Read the returned buffer
    result_content = read_scratchpad(agent_id, 0x100000)
    print(f"NtQuerySystemInformation = {hex(ntstatus)}")
    return {
        "retval": ntstatus,
        "raw_buffer": result_content
    }