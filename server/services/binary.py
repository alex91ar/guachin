import struct
from models.syscall import Syscall
from models.agent import Agent

OBJ_CASE_INSENSITIVE = 0x00000040

def align_up(value: int, alignment: int) -> int:
    return (value + (alignment - 1)) & ~(alignment - 1)

import struct


def to_unicode(object_text):
    return object_text.encode("utf-16-le") + b"\x00\x00"


def build_ptr(base_address, data, align=16):
    print(f"build_ptr(base_address={hex(base_address)}, data={data.hex()}, align={align})")
    data_size = align_up(len(data), align)
    blob = bytearray(data_size)
    blob[:len(data)] = data
    return blob, base_address + data_size


def build_unicode_string(base_address, object_text):
    """
    Build an x64 UNICODE_STRING followed by its UTF-16LE buffer.

    Layout:
        +0x00 USHORT Length
        +0x02 USHORT MaximumLength
        +0x04 ULONG  padding
        +0x08 PWSTR  Buffer
        +0x10 WCHAR[] UTF-16LE string including trailing NUL

    Returns:
        (blob, next_ptr)
    """
    object_text_unicode = to_unicode(object_text)

    # On x64, the UTF-16 buffer starts immediately after the 16-byte struct.
    string_ptr = base_address + 0x10

    blob = bytearray()
    blob.extend(struct.pack("<H", len(object_text_unicode) - 2))  # Length, excluding NUL
    blob.extend(struct.pack("<H", len(object_text_unicode)))      # MaximumLength, including NUL
    blob.extend(struct.pack("<I", 0))                             # x64 padding
    blob.extend(struct.pack("<Q", string_ptr))                    # Buffer
    blob.extend(object_text_unicode)

    unicode_str_data, next_ptr = build_ptr(base_address, blob)

    print(
        f"build_unicode_string("
        f"base_address={hex(base_address)}, "
        f"text={object_text!r}, "
        f"Length={hex(len(object_text_unicode) - 2)}, "
        f"MaximumLength={hex(len(object_text_unicode))}, "
        f"Buffer={hex(string_ptr)}, "
        f"next_ptr={hex(next_ptr)}) = {unicode_str_data.hex()}"
    )

    return unicode_str_data, next_ptr



def build_object_attributes(base_address, object_name, attributes =0):
    """
    Build an x64 OBJECT_ATTRIBUTES followed by the UNICODE_STRING blob it points to.

    OBJECT_ATTRIBUTES layout on x64:
        +0x00 ULONG  Length
        +0x04 ULONG  padding
        +0x08 HANDLE RootDirectory
        +0x10 PUNICODE_STRING ObjectName
        +0x18 ULONG  Attributes
        +0x1C ULONG  padding
        +0x20 PVOID  SecurityDescriptor
        +0x28 PVOID  SecurityQualityOfService

    Returns:
        (blob, next_ptr)
    """
    object_attributes_size = 48
    unicode_base = base_address + object_attributes_size

    unicode_str_data, next_ptr = build_unicode_string(unicode_base, object_name)

    blob = bytearray(object_attributes_size)

    # Length
    blob[0:4] = (object_attributes_size).to_bytes(4, "little")

    # RootDirectory = NULL
    blob[8:16] = (0).to_bytes(8, "little")

    # ObjectName = pointer to embedded UNICODE_STRING
    blob[16:24] = (unicode_base).to_bytes(8, "little")

    # Attributes = 0
    blob[24:28] = (0).to_bytes(attributes, "little")

    # SecurityDescriptor = NULL
    blob[32:40] = (0).to_bytes(8, "little")

    # SecurityQualityOfService = NULL
    blob[40:48] = (0).to_bytes(8, "little")

    full_blob = blob + unicode_str_data

    print(
        f"build_object_attributes("
        f"base_address={hex(base_address)}, "
        f"object_name={object_name!r}, "
        f"ObjectName={hex(unicode_base)}, "
        f"next_ptr={hex(next_ptr)}) = {full_blob.hex()}"
    )

    return full_blob, next_ptr


def build_ps_create_info(ptr):
    """
    Build a zero-initialized PS_CREATE_INFO for x64.

    The caller can patch more fields if needed.
    """
    size = 88
    data = bytearray(size)

    # Size
    struct.pack_into("<Q", data, 0x00, size)

    # State = PsCreateInitialState
    # This is typically 0 for input to NtCreateUserProcess.
    struct.pack_into("<I", data, 0x08, 0)

    # InitFlags at +0x0C
    # Keep zero unless you intentionally want specific creation semantics.
    struct.pack_into("<I", data, 0x0C, 0)

    print(f"build_ps_create_info(ptr={hex(ptr)}) = {data.hex()}")
    return bytes(data), ptr + size


def build_ps_attribute_list(ptr, image_path_ptr, image_path_len, handle_list_ptr, handle_list_len):
    """
    Build a PS_ATTRIBUTE_LIST with:
      - PS_ATTRIBUTE_IMAGE_NAME
      - PS_ATTRIBUTE_HANDLE_LIST

    x64 PS_ATTRIBUTE:
        ULONG_PTR Attribute
        SIZE_T    Size
        union {
            ULONG_PTR Value
            PVOID     ValuePtr
        }
        PSIZE_T   ReturnLength

    Each entry is 32 bytes on x64.
    Total for 2 attrs + TotalLength header:
        8 + (2 * 32) = 72 bytes
    """
    PS_ATTRIBUTE_IMAGE_NAME = 0x20005
    PS_ATTRIBUTE_HANDLE_LIST = 0x20002

    entries = [
        (PS_ATTRIBUTE_IMAGE_NAME, image_path_len, image_path_ptr, 0),
        (PS_ATTRIBUTE_HANDLE_LIST, handle_list_len, handle_list_ptr, 0),
    ]

    total_length = 8 + (len(entries) * 32)

    data = bytearray()
    data.extend(struct.pack("<Q", total_length))

    for attribute, size, value_ptr, return_length in entries:
        data.extend(struct.pack("<Q", attribute))
        data.extend(struct.pack("<Q", size))
        data.extend(struct.pack("<Q", value_ptr))
        data.extend(struct.pack("<Q", return_length))

    print(
        f"build_ps_attribute_list("
        f"ptr={hex(ptr)}, "
        f"TotalLength={hex(total_length)}, "
        f"ImageNamePtr={hex(image_path_ptr)}, "
        f"ImageNameLen={hex(image_path_len)}, "
        f"HandleListPtr={hex(handle_list_ptr)}, "
        f"HandleListLen={hex(handle_list_len)}) = {data.hex()}"
    )

    return bytes(data), ptr + total_length

def push_rtl(address, params, debug=False):
    bytecode = bytearray()


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
    if debug:
        bytecode.extend(b'\xCC')  # int3
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
