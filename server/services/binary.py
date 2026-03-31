import struct
from models.syscall import Syscall
from models.agent import Agent

OBJ_CASE_INSENSITIVE = 0x00000040

def align_up(value: int, alignment: int) -> int:
    return (value + (alignment - 1)) & ~(alignment - 1)

def build_ps_create_info(ptr):
    """88-byte structure for process creation state."""
    data = bytearray(88)
    struct.pack_into('<Q', data, 0, 88) # Size
    struct.pack_into('<I', data, 12, 0x00000003) # StateFlags: WriteOutput/Input Allowed
    return bytes(data), ptr + 88

def build_ps_attribute_list(ptr, image_path_ptr, image_path_len, handle_list_ptr, handle_list_len):
    """Builds a list with 2 attributes: Image Name and Handle List."""
    header = struct.pack('<Q', 72)
    # Attr 1: Image Name (0x20005)
    attr1 = struct.pack('<QQQQ', 0x20005, image_path_len, image_path_ptr, 0)
    # Attr 2: Handle List (0x20002)
    attr2 = struct.pack('<QQQQ', 0x20002, handle_list_len, handle_list_ptr, 0)
    
    data = header + attr1 + attr2
    return data, ptr + 72

def build_unicode_string(base_address, text) -> bytearray:
    """
    Build a 64-bit UNICODE_STRING + UTF-16 string as a bytearray.

    Layout:
        UNICODE_STRING (16 bytes)
        UTF-16LE string (N bytes, NUL-terminated)

    Parameters:
        base_address: where this blob will live in memory
        text: Python string

    Returns:
        bytearray
    """
    text = to_unicode(text)
    text_blob = bytearray(align_up(len(text), 8))
    text_blob[:len(text)] = text
    
    blob = bytearray(16)

    # UNICODE_STRING (64-bit)
    # 0x00 USHORT Length
    # 0x02 USHORT MaximumLength
    # 0x04 ULONG padding
    # 0x08 PWSTR Buffer

    blob[0x00:0x02] = struct.pack("<H", len(text)-2)
    blob[0x02:0x04] = struct.pack("<H", len(text))
    # 0x04–0x08 is padding (leave zero)
    blob[0x08:0x10] = struct.pack("<Q", base_address+16)
    blob.extend(text_blob)
    print(f"build_unicode_string(base_address={hex(base_address)}, text={text_blob.hex()})")
    return blob, base_address+len(blob)

def to_unicode(text):
    text_bytes = text.encode("utf-16-le")
    text_bytes_nul = text_bytes + b"\x00\x00"
    return text_bytes_nul

def build_object_attributes(base_address, object_name_addr):
    """
    Builds an x64 OBJECT_ATTRIBUTES structure as a bytearray.

    Returns:
        bytearray: 48-byte OBJECT_ATTRIBUTES structure
    """
    blob = bytearray(48)

    # Length (ULONG, 4 bytes)
    blob[0:4] = (48).to_bytes(4, "little")

    # Padding (4 bytes) → already zero

    # RootDirectory (HANDLE, 8 bytes)
    blob[8:16] = int(0).to_bytes(8, "little")

    # ObjectName (PUNICODE_STRING, 8 bytes)
    blob[16:24] = object_name_addr.to_bytes(8, "little")

    # Attributes (ULONG, 4 bytes)
    blob[24:28] = int(0).to_bytes(4, "little")

    # Padding (4 bytes) → already zero

    # SecurityDescriptor (PVOID, 8 bytes)
    blob[32:40] = int(0).to_bytes(8, "little")

    # SecurityQualityOfService (PVOID, 8 bytes)
    blob[40:48] = int(0).to_bytes(8, "little")

    print(f"build_object_attributes(object_name_addr = {hex(object_name_addr)})")
    return blob, base_address + len(blob)


def build_ptr(base_address, data, align=16):
    print(f"build_ptr base_address = {hex(base_address)}, data = {data.hex()}, align = {align}")
    data_size = align_up(len(data), align)
    blob = bytearray(data_size)
    blob[0:len(data)] = data
    return blob, base_address + len(blob)

import struct

def push_rtl(address, params, debug=False):
    bytecode = bytearray()

    if debug:
        bytecode.extend(b'\xCC')  # int3

    extra_count = max(0, len(params) - 4)

    # 32 bytes shadow space + 8 bytes per extra arg
    stack_size = 0x20 + (extra_count * 8)

    # round up to nearest 16 for alignment
    if stack_size % 16 != 0:
        stack_size += 8

    # push rbp
    bytecode.extend(b'\x55')

    # mov rbp, rsp
    bytecode.extend(b'\x48\x89\xE5')

    # sub rsp, stack_size
    if stack_size <= 0x7F:
        bytecode.extend(b'\x48\x83\xEC')
        bytecode.extend(struct.pack('<B', stack_size))
    else:
        bytecode.extend(b'\x48\x81\xEC')
        bytecode.extend(struct.pack('<I', stack_size))

    # Write extra arguments (5th and above) into stack slots
    # [rsp+0x20] = 5th arg
    # [rsp+0x28] = 6th arg
    # ...
    for i, param in enumerate(params[4:]):
        offset = 0x20 + (i * 8)

        # mov rax, imm64
        bytecode.extend(b'\x48\xB8')
        bytecode.extend(struct.pack('<Q', param))

        # mov [rsp+offset], rax
        if offset <= 0x7F:
            bytecode.extend(b'\x48\x89\x44\x24')
            bytecode.extend(struct.pack('<B', offset))
        else:
            raise ValueError("Too many parameters for this simple encoder")

    # Load parameters 1-4 into RCX, RDX, R8, R9
    regs = [
        b'\x48\xB9',  # mov rcx, imm64
        b'\x48\xBA',  # mov rdx, imm64
        b'\x49\xB8',  # mov r8,  imm64
        b'\x49\xB9',  # mov r9,  imm64
    ]

    for i in range(min(len(params), 4)):
        bytecode.extend(regs[i])
        bytecode.extend(struct.pack('<Q', params[i]))

    # mov rax, address
    bytecode.extend(b'\x48\xB8')
    bytecode.extend(struct.pack('<Q', address))

    # call rax
    bytecode.extend(b'\xFF\xD0')

    # mov rsp, rbp
    bytecode.extend(b'\x48\x89\xEC')

    # pop rbp
    bytecode.extend(b'\x5D')

    # ret
    bytecode.extend(b'\xC3')

    return bytes(bytecode)

def push_syscall(syscall_number, params, debug = False):
    bytecode = bytearray()
    bytecode.extend(b'\x53')      # push rbx
    bytecode.extend(b'\x55')      # push rbp
    bytecode.extend(b'\x57')      # push rdi
    bytecode.extend(b'\x56')      # push rsi
    bytecode.extend(b'\x41\x54')  # push r12
    bytecode.extend(b'\x41\x55')  # push r13
    bytecode.extend(b'\x41\x56')  # push r14
    bytecode.extend(b'\x41\x57')  # push r15
    # 1. PUSH Extra Parameters (5 and above) FIRST
    # These must be pushed in REVERSE order (right-to-left)
    if len(params) > 4:
        for param in reversed(params[4:]):
            # MOV RAX, imm64
            bytecode.extend(b'\x48\xb8')
            bytecode.extend(struct.pack('<Q', param))
            # PUSH RAX
            bytecode.extend(b'\x50')


    # 2. ALLOCATE SHADOW SPACE (0x20 bytes) LAST
    # This pushes 0x0 4 times.
    bytecode.extend(b'\x6A\x00')
    bytecode.extend(b'\x6A\x00')
    bytecode.extend(b'\x6A\x00')
    bytecode.extend(b'\x6A\x00')

    # 3. Load Parameters 1-4 into Registers (RCX, RDX, R8, R9)
    regs = [b'\x48\xb9', b'\x48\xba', b'\x49\xb8', b'\x49\xb9']
    for i in range(min(len(params), 4)):
        bytecode.extend(regs[i])
        bytecode.extend(struct.pack('<Q', params[i]))

    # 4. Set Syscall Number (MOV EAX, syscall_id)
    bytecode.extend(b"\x49\x89\xca")
    bytecode.extend(b'\xb8')
    bytecode.extend(struct.pack('<I', syscall_number))
    # 5. This pushes 0x0
    bytecode.extend(b'\x6A\x00')
    # 6. Syscall Instruction
    if debug:
        bytecode.extend(b'\xcc')
    bytecode.extend(b'\x0f\x05')
    # Align stack 
    bytecode.extend(b"\x48\x83\xc4")
    stack_align = 0x28
    if len(params) > 4:
        stack_align +=8*(len(params)-4)
    bytecode.extend(struct.pack('<B',stack_align))

    bytecode.extend(
    b'\x41\x5f'      # pop r15
    b'\x41\x5e'      # pop r14
    b'\x41\x5d'      # pop r13
    b'\x41\x5c'      # pop r12
    b'\x5e'          # pop rsi
    b'\x5f'          # pop rdi
    b'\x5d'          # pop rbp
    b'\x5b'          # pop rbx
    )
    # 7. ret
    bytecode.extend(b'\xc3')

    return (bytes(bytecode))



def readmemory(address, size):
    retmessage = bytearray()
    retmessage.extend(b'\x01')
    retmessage.extend(struct.pack('<Q', address))
    retmessage.extend(struct.pack('<Q', size))
    return retmessage

def getPtrs(base_address, imagepathname, commandline):
    imagepathname_data, commandline_ptr = build_unicode_string(base_address, imagepathname)
    commandline_data, process_parameters_ptr = build_unicode_string(commandline_ptr, commandline)
    process_parameters_data, next_ptr = build_ptr(process_parameters_ptr, b"\x00\x00\x00\x00\x00\x00\x00\x00")
    return imagepathname_data + commandline_data + process_parameters_data, base_address, commandline_ptr, process_parameters_ptr

def rtlCreateProcessParametersEx(agent_id, ImagePathName_add, CommandLine_add, process_parameters_add):
    agent = Agent.by_id(agent_id)
    rtl_add = Syscall.sys(agent.id, "RtlCreateProcessParametersEx")
    scratchpad = agent.scratchpad
    process_parameters_data, next_ptr = build_ptr(scratchpad, int.to_bytes(process_parameters_add, 8, byteorder="little"))

    dllpath = 0
    currentdirectory = 0
    environment = 0
    windowtitle = 0
    desktopinfo = 0
    shellinfo = 0
    runtimedata = 0
    flags = 0x1 # RTL_USER_PROC_PARAMS_NORMALIZED
    params = [
        scratchpad,
        ImagePathName_add,
        dllpath,
        currentdirectory,
        CommandLine_add,
        environment,
        windowtitle,
        desktopinfo,
        shellinfo,
        runtimedata,
        flags
    ]
    shellcode = push_rtl(rtl_add, params)
    print(f"RtlCreateProcessParametersEx(process_parameters_add={hex(scratchpad)}, image_path_name_unicode_add={hex(ImagePathName_add)}, dllpath=0x0, currentdirectory=0x0, command_line_unicode_add={hex(CommandLine_add)}, environment=0x0, windowtitle=0x0, desktopinfo=0x0, shellinfo=0x0, runtimedata=0x0, flags=0x1)")
    data = process_parameters_data
    return data, shellcode

    


def ntCreateUserProcess(agent_id, process_parameters_add, write_pipe, image_path):
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtCreateUserProcess")
    scratchpad = agent.scratchpad
    processhandle_data, threadhandle_ptr = build_ptr(scratchpad, b"\x00\x00\x00\x00\x00\x00\x00\x00")
    threadhandle_data, image_path_name_ptr = build_ptr(threadhandle_ptr, b"\x00\x00\x00\x00\x00\x00\x00\x00")
    image_path_name_unicode_data, write_pipe_ptr = build_unicode_string(image_path_name_ptr,image_path)
    write_pipe_data, CreateInfo_ptr = build_ptr(write_pipe_ptr, write_pipe.to_bytes(8, byteorder="little", signed=False))
    ProcessDesiredAccess = 0x001F0FFF # PROCESS_ALL_ACCESS
    ThreadDesiredAccess = 0x001F03FF # THREAD_ALL_ACCESS
    ProcessAttr = 0
    ThreadAttr = 0 
    ProcessFlags = 0x00000004 # PROCESS_CREATE_FLAGS_INHERIT_HANDLES
    ThreadFlags = 0
    CreateInfo_data, AttributeList_ptr = build_ps_create_info(CreateInfo_ptr)
    AttributeList_data, next_ptr = build_ps_attribute_list(AttributeList_ptr, image_path_name_ptr+16, len(image_path)*2, write_pipe_ptr)
    params = [
        scratchpad,
        threadhandle_ptr,
        ProcessDesiredAccess,
        ThreadDesiredAccess,
        ProcessAttr,
        ThreadAttr,
        ProcessFlags,
        ThreadFlags,
        process_parameters_add,
        CreateInfo_ptr,
        AttributeList_ptr
    ]
    shellcode = push_syscall(syscall, params)
    print(f"ntCreateUserProcess(ProcessHandle={hex(scratchpad)},ThreadHandle={hex(threadhandle_ptr)},ProcessDesiredAccess={hex(ProcessDesiredAccess)},ThreadDesiredAccess={hex(ThreadDesiredAccess)},ProcessObjectAttributes={hex(ProcessAttr)},ThreadObjectAttributes={hex(ThreadAttr)},ProcessFlags={hex(ProcessFlags)},ThreadFlags={hex(ThreadFlags)},ProcessParameters={hex(process_parameters_add)},CreateInfo={hex(CreateInfo_ptr)},AttributeList={hex(AttributeList_ptr)})")
    data = processhandle_data +  threadhandle_data + image_path_name_unicode_data + write_pipe_data + CreateInfo_data + AttributeList_data
    return data, shellcode
    