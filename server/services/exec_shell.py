from services.binary import readmemory, allocmem, push_syscall, PTR, push_rtl_func
from models.agent import Agent
from models.syscall import Syscall
from services.orders import send_and_wait, read_from_agent

def createPipe(agent_id):
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtCreateFile")
    params = [agent.scratchpad, # &FileHandle
              0xC0100000, # 0x80000000 | 0x40000000 | 0x00100000
              agent.scratchpad+8, # &ObjAttributes
              agent.scratchpad+16, # &IoStatusBlock
              0, # AllocationSize
              0x80, # FileAttributes
              0x07, # ShareAccess
              0x02, # CreateDisposition
              0x20, # CreateOptions
              0, # EaBuffer
              0, # EaLength
             ]
    shellcode = push_syscall(syscall, params)
    ntstatus = send_and_wait(agent_id, shellcode, True)
    pipe_handle = read_from_agent(agent_id, agent.scratchpad, 8)
    return ntstatus, pipe_handle

def rtlCreateProcessParametersEx(agent_id, proc_params_add, unicode_image_name, commandline):
    agent = Agent.by_id(agent_id)
    func_add = Syscall.sys(agent.id, "RtlCreateProcessParametersEx")
    params = [proc_params_add, # ProcessParameters
              PTR(unicode_image_name, agent.scratchpad), # ImagePathName
              0, # DllPath
              0, # CurrentDirectory
              PTR(commandline, agent.scratchpad + len(unicode_image_name)), # CommandLine
              0, # Environment
              0, # WindowTitle
              0, # DesktopInfo
              0, # ShellInfo
              0, # RuntimeData
              0x1] # Flags = RTL_USER_PROC_PARAMS_NORMALIZED
    shellcode = push_rtl_func(func_add, params)
    return send_and_wait(agent_id, shellcode)

def allocate_memory(agent_id, size, protection):
    retparams, shellcode = allocmem(agent_id, size, protection)
    response_data = send_and_wait(agent_id, shellcode)
    print(f"Response from NtAllocateVirtualMemory = 0x{response_data.hex()}")
    return response_data, read_from_agent(agent_id, retparams[0], 8) # retparams[0] contains BaseAddress