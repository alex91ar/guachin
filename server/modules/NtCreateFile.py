NAME = "NtCreateFile"
DESCRIPTION = "Create a file in the target agent"
PARAMS = [
    {"name":"filename", "description":"Name of file to be created", "type":"str"},
    {"name": "desired_access", "description": "Desired access mask", "type": "hex"} 
]

def NtCreateFile(agent_id, name, desired_access):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, build_object_attributes, push_syscall
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtCreateFile")
    scratchpad = agent.scratchpad
    filehandle_data, object_attributes_ptr = build_ptr(scratchpad, b"\x00\x00\x00\x00\x00\x00\x00\x00")
    object_attributes_data, status_block_ptr = build_object_attributes(object_attributes_ptr, unicode_str_ptr)
    status_block_data,  next_ptr = build_ptr(status_block_ptr,b"\x00\x00\x00\x00\x00\x00\x00\x00")
    params = [scratchpad, # &FileHandle
              desired_access, # FILE_ALL_ACCCESS
              object_attributes_ptr, # &ObjAttributes
              status_block_ptr, # &IoStatusBlock
              0, # AllocationSize
              0x80, # FileAttributes
              0x07, # ShareAccess
              0x03, # CreateDisposition
              0x20, # CreateOptions
              0, # EaBuffer
              0, # EaLength
             ]
    shellcode = push_syscall(syscall, params, agent.debug)
    data = filehandle_data + object_attributes_data + status_block_data
    print(f"NtCreateFile(FileHandle={hex(scratchpad)}, DesiredAccess={hex(desired_access)}, ObjAttr={hex(object_attributes_ptr)}, IoStatus={hex(status_block_ptr)}, AllocSize=0x0, FileAttributes=0x80, ShareAccess=0x07, CreateDisposition=0x02, CreateOptions=0x20, EaBuffer=0x0, EaLength=0x0)")
    return data, shellcode

def createFile(agent_id, name, desired_access):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    data, shellcode = NtCreateFile(agent_id, name, desired_access)
    write_scratchpad(agent_id, data)
    response_data = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    scratchpad = read_scratchpad(agent_id, 4)
    file_handle = int.from_bytes(scratchpad[:4], 'little')
    print(f"Response from NtCreateFile = {hex(response_data)}, file_handle = {hex(file_handle)}")
    return response_data, file_handle

def function(agent_id, args):
    retval, file_handle = createFile(agent_id, args[0], args[1])
    return {"retval":retval, "FILE_HANDLE":file_handle}