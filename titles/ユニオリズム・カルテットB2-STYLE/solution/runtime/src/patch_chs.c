#include <windows.h>
#include <string.h>

__declspec(dllexport) void dummy(void) {}

static LONG g_font_hook_count = 0;
static LONG g_file_hook_count = 0;
static LONG g_font_a_hook_count = 0;

static BOOL get_module_dir_w(wchar_t *buffer, DWORD size)
{
    DWORD len;
    wchar_t *slash;
    if (!buffer || size == 0)
        return FALSE;
    len = GetModuleFileNameW(NULL, buffer, size);
    if (!len || len >= size)
        return FALSE;
    slash = wcsrchr(buffer, L'\\');
    if (!slash)
        return FALSE;
    *slash = L'\0';
    return TRUE;
}

static BOOL build_absolute_path_w(LPCWSTR relative_path, wchar_t *buffer, DWORD size)
{
    wchar_t module_dir[MAX_PATH * 4] = { 0 };
    if (!get_module_dir_w(module_dir, MAX_PATH * 4))
        return FALSE;
    if (wsprintfW(buffer, L"%s\\%s", module_dir, relative_path) <= 0)
        return FALSE;
    return TRUE;
}

static BOOL build_absolute_basename_path_w(LPCSTR path_name, wchar_t *buffer, DWORD size)
{
    const char *base_name;
    wchar_t base_name_w[MAX_PATH] = { 0 };
    if (!path_name || !path_name[0])
        return FALSE;
    base_name = strrchr(path_name, '\\');
    if (!base_name)
        base_name = strrchr(path_name, '/');
    base_name = base_name ? base_name + 1 : path_name;
    if (!MultiByteToWideChar(CP_ACP, 0, base_name, -1, base_name_w, MAX_PATH))
        return FALSE;
    return build_absolute_path_w(base_name_w, buffer, size);
}

static BOOL build_temp_log_path_w(wchar_t *buffer, DWORD size)
{
    DWORD len;
    if (!buffer || size == 0)
        return FALSE;
    len = GetTempPathW(size, buffer);
    if (!len || len >= size)
        return FALSE;
    if (wsprintfW(buffer + len, L"patch_chs.log") <= 0)
        return FALSE;
    return TRUE;
}

static void log_line(const char *text)
{
    wchar_t log_path[MAX_PATH * 4] = { 0 };
    HANDLE log_file;
    DWORD written = 0;
    DWORD len;
    if (!text)
        return;
    if (!build_temp_log_path_w(log_path, MAX_PATH * 4))
        return;
    log_file = CreateFileW(
        log_path,
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        NULL);
    if (log_file == INVALID_HANDLE_VALUE)
        return;
    len = (DWORD)strlen(text);
    WriteFile(log_file, text, len, &written, NULL);
    WriteFile(log_file, "\r\n", 2, &written, NULL);
    CloseHandle(log_file);
}

static void log_font_info(const LOGFONTA *log_font)
{
    char line[256];
    if (!log_font)
        return;
    wsprintfA(
        line,
        "CreateFontIndirectA charset=%u face=%s height=%ld weight=%ld",
        (unsigned int)(unsigned char)log_font->lfCharSet,
        log_font->lfFaceName,
        log_font->lfHeight,
        log_font->lfWeight);
    log_line(line);
}

static void log_font_a_info(
    int height,
    int weight,
    DWORD charset,
    LPCSTR face_name)
{
    char line[256];
    wsprintfA(
        line,
        "CreateFontA charset=%u face=%s height=%d weight=%d",
        (unsigned int)charset,
        face_name ? face_name : "(null)",
        height,
        weight);
    log_line(line);
}

static void log_create_file_a(const char *tag, const char *path_name, DWORD desired_access, DWORD creation_disposition)
{
    char line[1024];
    if (InterlockedIncrement(&g_file_hook_count) > 80)
        return;
    wsprintfA(
        line,
        "%s access=0x%08X disposition=0x%08X path=%s",
        tag,
        (unsigned int)desired_access,
        (unsigned int)creation_disposition,
        path_name ? path_name : "(null)");
    log_line(line);
}

static void log_create_file_w(const char *tag, const wchar_t *path_name, DWORD desired_access, DWORD creation_disposition)
{
    char path_a[1024] = { 0 };
    if (InterlockedIncrement(&g_file_hook_count) > 80)
        return;
    if (path_name)
        WideCharToMultiByte(CP_UTF8, 0, path_name, -1, path_a, sizeof(path_a), NULL, NULL);
    log_create_file_a(tag, path_name ? path_a : "(null)", desired_access, creation_disposition);
}

static void log_path_call(const char *tag, const char *path_name)
{
    char line[1024];
    if (InterlockedIncrement(&g_file_hook_count) > 120)
        return;
    wsprintfA(line, "%s path=%s", tag, path_name ? path_name : "(null)");
    log_line(line);
}

static int contains_ignore_case_a(const char *value, const char *pattern)
{
    size_t value_len;
    size_t pattern_len;
    size_t i;
    if (!value || !pattern)
        return 0;
    value_len = strlen(value);
    pattern_len = strlen(pattern);
    if (!pattern_len || value_len < pattern_len)
        return 0;
    for (i = 0; i <= value_len - pattern_len; ++i)
    {
        if (_strnicmp(value + i, pattern, pattern_len) == 0)
            return 1;
    }
    return 0;
}

static int should_log_create_file(const char *path_name, DWORD desired_access, DWORD creation_disposition)
{
    if (!path_name)
        return 1;
    if (desired_access & (GENERIC_WRITE | GENERIC_ALL))
        return 1;
    if (creation_disposition != OPEN_EXISTING)
        return 1;
    if (contains_ignore_case_a(path_name, "yssfs.dat"))
        return 1;
    if (contains_ignore_case_a(path_name, "save"))
        return 1;
    return 0;
}

static BOOL iat_hook_module(LPCSTR target_dll_name, LPCSTR module_dll_name, PROC org_proc, PROC new_proc)
{
#ifdef _WIN64
#define VA_TYPE ULONGLONG
#else
#define VA_TYPE DWORD
#endif
    DWORD old_protect = 0;
    VA_TYPE image_base = (VA_TYPE)GetModuleHandleA(module_dll_name);
    if (!image_base)
        return FALSE;

    LPBYTE nt_header = (LPBYTE)(*(DWORD *)((LPBYTE)image_base + 0x3C) + image_base);
#ifdef _WIN64
    VA_TYPE imp_descriptor_rva = *((DWORD *)&nt_header[0x90]);
#else
    VA_TYPE imp_descriptor_rva = *((DWORD *)&nt_header[0x80]);
#endif
    PIMAGE_IMPORT_DESCRIPTOR imp_descriptor = (PIMAGE_IMPORT_DESCRIPTOR)(image_base + imp_descriptor_rva);
    for (; imp_descriptor->Name; imp_descriptor++)
    {
        LPCSTR dll_name = (LPCSTR)(image_base + imp_descriptor->Name);
        if (_stricmp(dll_name, target_dll_name) != 0)
            continue;

        PIMAGE_THUNK_DATA first_thunk = (PIMAGE_THUNK_DATA)(image_base + imp_descriptor->FirstThunk);
        for (; first_thunk->u1.Function; first_thunk++)
        {
            if (first_thunk->u1.Function != (VA_TYPE)org_proc)
                continue;

            VirtualProtect((LPVOID)&first_thunk->u1.Function, sizeof(VA_TYPE), PAGE_EXECUTE_READWRITE, &old_protect);
            first_thunk->u1.Function = (VA_TYPE)new_proc;
            VirtualProtect((LPVOID)&first_thunk->u1.Function, sizeof(VA_TYPE), old_protect, &old_protect);
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL iat_hook(LPCSTR target_dll_name, PROC org_proc, PROC new_proc)
{
    return iat_hook_module(target_dll_name, NULL, org_proc, new_proc);
}

static int ends_with_ignore_case_a(const char *value, const char *suffix)
{
    size_t value_len = strlen(value);
    size_t suffix_len = strlen(suffix);
    if (value_len < suffix_len)
        return 0;
    return _stricmp(value + value_len - suffix_len, suffix) == 0;
}

static int ends_with_ignore_case_w(const wchar_t *value, const wchar_t *suffix)
{
    size_t value_len = wcslen(value);
    size_t suffix_len = wcslen(suffix);
    if (value_len < suffix_len)
        return 0;
    return _wcsicmp(value + value_len - suffix_len, suffix) == 0;
}

static int should_redirect_pack_open(DWORD desired_access, DWORD creation_disposition)
{
    if (creation_disposition != OPEN_EXISTING)
        return 0;
    if (desired_access & (GENERIC_WRITE | GENERIC_ALL))
        return 0;
    return 1;
}

static HANDLE WINAPI CreateFileA_hook(
    LPCSTR file_name,
    DWORD desired_access,
    DWORD share_mode,
    LPSECURITY_ATTRIBUTES security_attributes,
    DWORD creation_disposition,
    DWORD flags_and_attributes,
    HANDLE template_file)
{
    if (should_log_create_file(file_name, desired_access, creation_disposition))
        log_create_file_a("CreateFileA", file_name, desired_access, creation_disposition);
    if (file_name
        && should_redirect_pack_open(desired_access, creation_disposition)
        && ends_with_ignore_case_a(file_name, "pac\\update1.ypf"))
    {
        wchar_t redirect[MAX_PATH * 4] = { 0 };
        if (build_absolute_path_w(L"patch_chs\\pac\\update1.ypf", redirect, MAX_PATH * 4)
            && GetFileAttributesW(redirect) != INVALID_FILE_ATTRIBUTES)
        {
            log_line("redirect CreateFileA pac\\update1.ypf -> patch_chs\\pac\\update1.ypf");
            return CreateFileW(
                redirect,
                desired_access,
                share_mode,
                security_attributes,
                creation_disposition,
                flags_and_attributes,
                template_file);
        }
    }
    if (file_name && file_name[1] == ':')
    {
        wchar_t rebuilt_path[MAX_PATH * 4] = { 0 };
        if (build_absolute_basename_path_w(file_name, rebuilt_path, MAX_PATH * 4)
            && GetFileAttributesW(rebuilt_path) != INVALID_FILE_ATTRIBUTES)
        {
            log_line("rewrite CreateFileA absolute path -> module dir");
            return CreateFileW(
                rebuilt_path,
                desired_access,
                share_mode,
                security_attributes,
                creation_disposition,
                flags_and_attributes,
                template_file);
        }
    }
    return CreateFileA(file_name, desired_access, share_mode, security_attributes, creation_disposition, flags_and_attributes, template_file);
}

static HANDLE WINAPI CreateFileW_hook(
    LPCWSTR file_name,
    DWORD desired_access,
    DWORD share_mode,
    LPSECURITY_ATTRIBUTES security_attributes,
    DWORD creation_disposition,
    DWORD flags_and_attributes,
    HANDLE template_file)
{
    if (!file_name || desired_access & (GENERIC_WRITE | GENERIC_ALL) || creation_disposition != OPEN_EXISTING)
        log_create_file_w("CreateFileW", file_name, desired_access, creation_disposition);
    if (file_name
        && should_redirect_pack_open(desired_access, creation_disposition)
        && ends_with_ignore_case_w(file_name, L"pac\\update1.ypf"))
    {
        wchar_t redirect[MAX_PATH * 4] = { 0 };
        if (build_absolute_path_w(L"patch_chs\\pac\\update1.ypf", redirect, MAX_PATH * 4)
            && GetFileAttributesW(redirect) != INVALID_FILE_ATTRIBUTES)
        {
            log_line("redirect CreateFileW pac\\update1.ypf -> patch_chs\\pac\\update1.ypf");
            file_name = redirect;
        }
    }
    return CreateFileW(file_name, desired_access, share_mode, security_attributes, creation_disposition, flags_and_attributes, template_file);
}

static DWORD WINAPI GetModuleFileNameA_hook(HMODULE module, LPSTR file_name, DWORD size)
{
    const char *relative_exe = ".\\UQB2S_chs.exe";
    DWORD result = GetModuleFileNameA(module, file_name, size);
    if (!result || !file_name || !file_name[0])
        return result;

    if ((!module || module == GetModuleHandleW(NULL)) && size > strlen(relative_exe))
    {
        strncpy_s(file_name, size, relative_exe, _TRUNCATE);
        log_line("hook GetModuleFileNameA: relative path applied");
        return (DWORD)strlen(file_name);
    }

    char short_path[MAX_PATH * 4] = { 0 };
    DWORD short_len = GetShortPathNameA(file_name, short_path, sizeof(short_path));
    if (short_len && short_len < size)
    {
        strncpy_s(file_name, size, short_path, _TRUNCATE);
        log_line("hook GetModuleFileNameA: short path applied");
        return (DWORD)strlen(file_name);
    }
    log_path_call("GetModuleFileNameA", file_name);
    return result;
}

static BOOL WINAPI SetCurrentDirectoryA_hook(LPCSTR path_name)
{
    wchar_t module_dir[MAX_PATH * 4] = { 0 };
    (void)path_name;
    if (get_module_dir_w(module_dir, MAX_PATH * 4))
    {
        log_line("hook SetCurrentDirectoryA: module dir applied");
        return SetCurrentDirectoryW(module_dir);
    }
    return SetCurrentDirectoryA(path_name);
}

static DWORD WINAPI GetFileAttributesA_hook(LPCSTR file_name)
{
    log_path_call("GetFileAttributesA", file_name);
    if (file_name && file_name[1] == ':')
    {
        wchar_t rebuilt_path[MAX_PATH * 4] = { 0 };
        if (build_absolute_basename_path_w(file_name, rebuilt_path, MAX_PATH * 4))
            return GetFileAttributesW(rebuilt_path);
    }
    return GetFileAttributesA(file_name);
}

static BOOL WINAPI CreateDirectoryA_hook(LPCSTR path_name, LPSECURITY_ATTRIBUTES security_attributes)
{
    log_path_call("CreateDirectoryA", path_name);
    return CreateDirectoryA(path_name, security_attributes);
}

static BOOL WINAPI DeleteFileA_hook(LPCSTR file_name)
{
    log_path_call("DeleteFileA", file_name);
    return DeleteFileA(file_name);
}

static UINT WINAPI GetTempFileNameA_hook(LPCSTR path_name, LPCSTR prefix_string, UINT unique, LPSTR temp_file_name)
{
    log_path_call("GetTempFileNameA", path_name);
    if (path_name && path_name[1] == ':')
        return GetTempFileNameA(".", prefix_string, unique, temp_file_name);
    return GetTempFileNameA(path_name, prefix_string, unique, temp_file_name);
}

static HFONT WINAPI CreateFontIndirectA_hook(LOGFONTA *log_font)
{
    if (log_font)
    {
        if (InterlockedIncrement(&g_font_hook_count) <= 8)
        {
            log_font_info(log_font);
        }
        log_font->lfCharSet = GB2312_CHARSET;
        strncpy_s(log_font->lfFaceName, LF_FACESIZE, "宋体", _TRUNCATE);
    }
    return CreateFontIndirectA(log_font);
}

static HFONT WINAPI CreateFontA_hook(
    int height,
    int width,
    int escapement,
    int orientation,
    int weight,
    DWORD italic,
    DWORD underline,
    DWORD strike_out,
    DWORD char_set,
    DWORD out_precision,
    DWORD clip_precision,
    DWORD quality,
    DWORD pitch_and_family,
    LPCSTR face_name)
{
    if (InterlockedIncrement(&g_font_a_hook_count) <= 8)
        log_font_a_info(height, weight, char_set, face_name);
    return CreateFontA(
        height,
        width,
        escapement,
        orientation,
        weight,
        italic,
        underline,
        strike_out,
        GB2312_CHARSET,
        out_precision,
        clip_precision,
        quality,
        pitch_and_family,
        "宋体");
}

static void install_font_hook(void)
{
    iat_hook("GDI32.dll", (PROC)CreateFontIndirectA, (PROC)CreateFontIndirectA_hook);
    iat_hook("GDI32.dll", (PROC)CreateFontA, (PROC)CreateFontA_hook);
}

static void install_file_redirect_hook(void)
{
    iat_hook("KERNEL32.dll", (PROC)CreateFileA, (PROC)CreateFileA_hook);
    iat_hook("KERNEL32.dll", (PROC)CreateFileW, (PROC)CreateFileW_hook);
    iat_hook("KERNEL32.dll", (PROC)GetModuleFileNameA, (PROC)GetModuleFileNameA_hook);
    iat_hook("KERNEL32.dll", (PROC)SetCurrentDirectoryA, (PROC)SetCurrentDirectoryA_hook);
    iat_hook("KERNEL32.dll", (PROC)GetFileAttributesA, (PROC)GetFileAttributesA_hook);
    iat_hook("KERNEL32.dll", (PROC)CreateDirectoryA, (PROC)CreateDirectoryA_hook);
    iat_hook("KERNEL32.dll", (PROC)DeleteFileA, (PROC)DeleteFileA_hook);
    iat_hook("KERNEL32.dll", (PROC)GetTempFileNameA, (PROC)GetTempFileNameA_hook);
}

static void install_hooks(void)
{
    log_line("patch_chs attach");
    install_font_hook();
    install_file_redirect_hook();
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved)
{
    (void)module;
    (void)reserved;

    if (reason == DLL_PROCESS_ATTACH)
        install_hooks();

    return TRUE;
}
