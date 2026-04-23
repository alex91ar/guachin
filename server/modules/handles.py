NAME = "handles"
DESCRIPTION = "Enumerate all handles for all processes using ntdll!NtQuerySystemInformation(SystemHandleInformation)."
PARAMS = []

DEPENDENCIES = ["NtQuerySystemInformation"]
DEFAULT = True

def normalize_raw_buffer(raw_buffer):
    if raw_buffer is None:
        raise ValueError("raw_buffer is None")
    if isinstance(raw_buffer, (bytes, bytearray)):
        return bytes(raw_buffer)
    if isinstance(raw_buffer, list):
        return bytes(raw_buffer)
    if isinstance(raw_buffer, str):
        return bytes.fromhex(raw_buffer)
    raise TypeError(f"Unsupported raw_buffer type: {type(raw_buffer).__name__}")

def function(agent_id, args):
    import struct

    # SystemHandleInformation = 16
    SYSTEM_HANDLE_INFORMATION_CLASS = 16
    
    # The handle table is system-wide and typically very large. 
    # 1MB (1048576) is a safe starting point for modern Windows systems.
    ret = NtQuerySystemInformation(agent_id, [SYSTEM_HANDLE_INFORMATION_CLASS])

    if not ret:
        return {"retval": -1, "message": "NtQuerySystemInformation returned no result"}

    if ret.get("retval") != 0:
        return {"retval": -1, "message": f"NtQuerySystemInformation failed {ret.get('retval')}"}

    try:
        blob = normalize_raw_buffer(ret.get("raw_buffer"))
    except Exception as e:
        return {"retval": -1, "message": f"Failed to normalize raw_buffer: {e}"}

    # x64 SYSTEM_HANDLE_INFORMATION structure:
    # ULONG_PTR NumberOfHandles;             8 bytes
    # SYSTEM_HANDLE_TABLE_ENTRY_INFO[1]      Array starts here
    
    if len(blob) < 8:
        return {"retval": -1, "message": "Buffer too small to contain count"}

    number_of_handles = struct.unpack_from("<Q", blob, 0)[0]
    
    # SYSTEM_HANDLE_TABLE_ENTRY_INFO x64 (24 bytes):
    # USHORT  UniqueProcessId;               2
    # USHORT  CreatorBackTraceIndex;        2
    # UCHAR   ObjectTypeIndex;              1
    # UCHAR   HandleAttributes;             1
    # USHORT  HandleValue;                  2
    # PVOID   Object;                       8
    # ULONG   GrantedAccess;                4
    #
    handle_fmt = (
        "<"
        "H"      # UniqueProcessId
        "H"      # CreatorBackTraceIndex
        "B"      # ObjectTypeIndex
        "B"      # HandleAttributes
        "H"      # HandleValue
        "Q"      # Object (Pointer)
        "I"      # GrantedAccess
    )
    entry_size = struct.calcsize(handle_fmt)
    
    processes_map = {}
    offset = 8 # Skip the NumberOfHandles QWORD

    for _ in range(number_of_handles):
        if offset + entry_size > len(blob):
            break

        fields = struct.unpack_from(handle_fmt, blob, offset)
        
        pid = fields[0]
        obj_type = fields[2]
        h_value = fields[4]
        obj_ptr = fields[5]
        access = fields[6]

        handle_info = {
            "handle": hex(h_value),
            "type_index": obj_type,
            "object_ptr": hex(obj_ptr),
            "access_mask": hex(access)
        }

        if pid not in processes_map:
            processes_map[pid] = []
        
        processes_map[pid].append(handle_info)
        offset += entry_size

    # Reformat into a list for consistent API response
    result_data = []
    for pid, handle_list in processes_map.items():
        result_data.append({
            "pid": pid,
            "handle_count": len(handle_list),
            "handles": handle_list
        })

    return {
        "retval": 0,
        "total_handles_found": number_of_handles,
        "unique_process_count": len(result_data),
        "data": result_data
    }