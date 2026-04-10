NAME = "NtReadFile"
DESCRIPTION = "Read data from a file or pipe handle into a buffer"
PARAMS = [
    {"name":"file_handle", "description":"Handle to the file or pipe", "type":"int"},
    {"name":"buffer_ptr", "description":"Memory address to write the data into", "type":"hex"},
    {"name":"buffer_length", "description":"Number of bytes to read", "type":"hex"},
    {"name":"byte_offset", "description":"Offset to read from", "type":"hex", "optional":True, "default":"0"},
]

def NtReadFile(agent_id, h_file, offset, buffer_ptr, length):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    import struct

    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtReadFile") # Syscall 0x06
    scratchpad = agent.scratchpad # Used for the 16-byte IoStatusBlock
    
    # Parameter Setup (9 total for x64)
    # 1. RCX (R10): FileHandle
    # 2. RDX     : Event (NULL)
    # 3. R8      : ApcRoutine (NULL)
    # 4. R9      : ApcContext (NULL)
    # 5. [RSP+28]: &IoStatusBlock (16 bytes)
    # 6. [RSP+30]: Buffer (Our destination pointer)
    # 7. [RSP+38]: Length (Number of bytes to read)
    # 8. [RSP+40]: ByteOffset (NULL for pipes)
    # 9. [RSP+48]: Key (NULL)

    # We build the IoStatusBlock on the scratchpad
    iostatus_data, ByteOffset_ptr = build_ptr(scratchpad, b"\x00" * 16)
    ByteOffset_data, next_ptr = build_ptr(ByteOffset_ptr, int.to_bytes(offset, 8, byteorder='little'))
    if offset == 0:
        ByteOffset_ptr = 0
    params = [
        h_file,      # P1: R10
        0,           # P2: RDX
        0,           # P3: R8
        0,           # P4: R9
        scratchpad,  # P5: [RSP+0x28] (&IoStatusBlock)
        buffer_ptr,  # P6: [RSP+0x30] (Remote Buffer)
        length,      # P7: [RSP+0x38] (Size)
        ByteOffset_ptr,           # P8: [RSP+0x40] (ByteOffset - 0 for synchronous pipes)
        0            # P9: [RSP+0x48] (Key)
    ]

    # Generate shellcode for 9-parameter syscall
    shellcode = push_syscall(syscall, params, agent.debug)
    
    # Data to be written to scratchpad (&IoStatusBlock)
    data = iostatus_data + ByteOffset_data
    '''
    print
    f"NtReadFile("
    f"Handle={hex(h_file)}, "
    f"Event=0x0, "
    f"ApcRoutine=0x0, "
    f"ApcContext=0x0, "
    f"IoStatusBlock={hex(scratchpad)}, "
    f"Buffer={hex(buffer_ptr)}, "
    f"Length={length}, "
    f"ByteOffset={hex(ByteOffset_ptr) if ByteOffset_ptr else 'NULL'}, "
    f"Key=0x0)"
    )
    '''
    return data, shellcode

def readFile(agent_id, h_file, buffer_ptr, length, offset):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    # 1. Generate and write the syscall logic
    data, shellcode = NtReadFile(agent_id, h_file, offset, buffer_ptr, length)
    write_scratchpad(agent_id, data)
    
    # 2. Execute the syscall
    response_retval = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    # 3. Read back the IoStatusBlock to get actual bytes read
    # Offset 8-15 in IoStatusBlock is the 'Information' field (BytesRead count)
    status_raw = read_scratchpad(agent_id, 16)
    bytes_read = int.from_bytes(status_raw[8:16], 'little')
    
    #printf"retval: {hex(response_retval)}, Bytes Read: {bytes_read}")
    return response_retval, bytes_read

def function(agent_id, args):
    # args: [file_handle, buffer_ptr, buffer_length, byte_offset]
    retval, bytes_read = readFile(agent_id, args[0], args[1], args[2], args[3])
    return {"retval": retval, "BYTES_READ": bytes_read}