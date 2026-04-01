NAME = "NtWriteFile"
DESCRIPTION = "Write a buffer to a file"
PARAMS = [
    {"name":"file_handle", "description":"Handle of an open file", "type":"bytes"},
    {"name":"data_buffer", "description":"Address to memory with buffer", "type":"hex"},
    {"name":"buffer_len", "description":"Length to write", "type":"hex"},
    {"name":"byte_offset", "description":"Offset to write the file into", "type":"hex"},
]

def NtWriteFile(agent_id, handle, offset, buffer_ptr, length):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtWriteFile")
    scratchpad = agent.scratchpad
    FileHandle = handle
    Event = 0x0
    ApcRoutine = 0x0
    ApcContext = 0x0
    IoStatusBlock_data, ByteOffset_ptr = build_ptr(scratchpad, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
    ByteOffset_data, next_ptr = build_ptr(ByteOffset_ptr, int.to_bytes(offset, 8, byteorder='little'))
    Key = 0x0
    params = [FileHandle,
              Event,
              ApcRoutine,
              ApcContext,
              scratchpad,
              buffer_ptr,
              length,
              ByteOffset_ptr,
              Key
             ]
    shellcode = push_syscall(syscall, params, agent.debug)
    data = IoStatusBlock_data + ByteOffset_data
    printval = "NtWriteFile("
    for param in params:
        printval += hex(param) + ", "
    printval += ")"
    print(printval)
    return data, shellcode

def writeFile(agent_id, handle, offset, buffer, length):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    data, shellcode = NtWriteFile(agent_id, handle, offset, buffer, length)
    write_scratchpad(agent_id, data)
    response_data = int.from_bytes(send_and_wait(agent_id, shellcode), byteorder='little')
    scratchpad = read_scratchpad(agent_id, 16)
    io_status_block = scratchpad[:16]
    print(f"Response from NtWriteFile = {hex(response_data)}, io_status_block = {io_status_block.hex()}")
    return response_data, io_status_block

def function(agent_id, args):
    retval, io_status_block = writeFile(agent_id, args[0], args[1], args[2], args[3])
    return {"retval":retval, "io_status_block":io_status_block}