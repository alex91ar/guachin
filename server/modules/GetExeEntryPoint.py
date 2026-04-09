NAME = "GetExeEntryPoint"
DESCRIPTION = "Parse the AddressOfEntryPoint from a PE file using Native reads"
PARAMS = [
    {"name":"file_path", "description":"Native path to EXE", "type":"str"}
]
DEPENDENCIES = [
    "read"
]

def function(agent_id, args):
    from services.orders import send_and_wait, read_from_agent
    import struct
    file_path = args[0]

    retval = read(agent_id, [file_path, 64, 0])
    if retval["retval"] == 0:
        data = retval["data"]
        if data[:2] != b'MZ':
            return {"retval": 0}
        print("1e09u309jf")
        # 3. GET OFFSET TO NT HEADERS (e_lfanew is at 0x3C)
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]

        # 4. READ NT HEADERS (Start at e_lfanew, read enough for OptionalHeader)
        # We read 256 bytes to be safe
        nt_headers = read(agent_id, [file_path, 256, e_lfanew])
        if nt_headers["retval"] == 0:
            # Verify PE Signature (at start of NT Headers)
            nt_headers = nt_headers["data"]
            if nt_headers[:4] != b'PE\x00\x00':
                return {"retval": "Invalid PE signature"}

            # 5. PARSE ENTRY POINT AND IMAGE BASE (x64 specific)
            # AddressOfEntryPoint is at NT_Header + 0x28 (Relative Virtual Address)
            # ImageBase is at NT_Header + 0x30 (64-bit)
            entry_point_rva = struct.unpack_from("<I", nt_headers, 0x28)[0]
            image_base_val  = struct.unpack_from("<Q", nt_headers, 0x30)[0]

            return {
                "retval": 0,
                "AddressOfEntryPoint": entry_point_rva,
                "ImageBase": image_base_val,
                "EntryAddress": image_base_val + entry_point_rva # The RIP starting point
            }
    return {
        "retval":"Error"
    }
