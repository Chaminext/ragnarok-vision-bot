"""
Read-only Ragnarok memory probe.

This is intentionally isolated from ro_bot.py. It only reads process memory and
prints JSON snapshots so we can validate whether the supplied offsets work on
the current client before considering any integration.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import struct
import sys
import time
from ctypes import wintypes


# Offsets copied from the experimental Go probe.
SINGLETON_BASE = 0x119FE28
LOCAL_PLAYER_GID = 0x158356C
LOCAL_PLAYER_AID = 0x1583570
LOCAL_MAP_NAME = 0x1583574
LOCAL_HP = 0x15874D0
LOCAL_SP = 0x15874D4
LOCAL_MAXHP = 0x15874D8
LOCAL_MAXSP = 0x15874DC

OFFSET_MANAGER_PTR = 0x04
OFFSET_INIT_FLAG = 0x58
OFFSET_ACTORLIST = 0xCC
OFFSET_LOCAL_ACTOR = 0x2C
OFFSET_LIST_HEAD = 0x10

ACTOR_GID = 0x110
ACTOR_WORLD_X = 0x10
ACTOR_WORLD_Y = 0x18
ACTOR_TYPE = 0x70
ACTOR_SCREEN_X = 0x0AC
ACTOR_SCREEN_Y = 0x0B0


TYPE_PLAYER = 0
TYPE_NPC = 1
TYPE_ITEM = 2
TYPE_MOB = 5
TYPE_PET = 7

TYPE_NAMES = {
    TYPE_PLAYER: "player",
    TYPE_NPC: "npc",
    TYPE_ITEM: "item",
    TYPE_MOB: "mob",
    TYPE_PET: "pet",
}


PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * MAX_PATH),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
kernel32.Module32FirstW.restype = wintypes.BOOL
kernel32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
kernel32.Module32NextW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
user32.EnumWindows.argtypes = None
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD


def winerr(prefix: str) -> RuntimeError:
    return RuntimeError(f"{prefix}: WinError {ctypes.get_last_error()}")


def iter_processes() -> list[tuple[int, str]]:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        raise winerr("CreateToolhelp32Snapshot failed")
    rows = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            rows.append((int(entry.th32ProcessID), entry.szExeFile))
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return rows


def find_process(names: list[str]) -> tuple[int, str]:
    wanted = {name.lower() for name in names}
    for pid, exe in iter_processes():
        if exe.lower() in wanted:
            return pid, exe
    raise RuntimeError(f"process not found: {', '.join(names)}")


def find_process_by_window_title(title_substring: str) -> tuple[int, str]:
    needle = title_substring.lower()
    found = {"pid": 0, "title": ""}

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @enum_proc
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if needle in title.lower():
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found["pid"] = int(pid.value)
            found["title"] = title
            return False
        return True

    user32.EnumWindows(callback, 0)
    if not found["pid"]:
        raise RuntimeError(f"window not found: {title_substring}")
    return found["pid"], f"window:{found['title']}"


def iter_modules(pid: int) -> list[dict]:
    flags = TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32
    snap = kernel32.CreateToolhelp32Snapshot(flags, pid)
    if snap == INVALID_HANDLE_VALUE:
        raise winerr("CreateToolhelp32Snapshot modules failed")
    modules = []
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(MODULEENTRY32W)
        ok = kernel32.Module32FirstW(snap, ctypes.byref(entry))
        while ok:
            base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value or 0
            modules.append({
                "name": entry.szModule,
                "path": entry.szExePath,
                "base": base,
                "base_hex": f"0x{base:X}",
                "size": int(entry.modBaseSize),
            })
            ok = kernel32.Module32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return modules


def choose_module_base(pid: int, module_name: str = "") -> tuple[int, str]:
    modules = iter_modules(pid)
    if not modules:
        return 0, ""
    if module_name:
        wanted = module_name.lower()
        for module in modules:
            if module["name"].lower() == wanted:
                return module["base"], module["name"]
        for module in modules:
            if wanted in module["name"].lower() or wanted in module["path"].lower():
                return module["base"], module["name"]
    first = modules[0]
    return first["base"], first["name"]


class Memory:
    def __init__(self, pid: int):
        access = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION
        self.pid = pid
        self.handle = kernel32.OpenProcess(access, False, pid)
        if not self.handle:
            raise winerr("OpenProcess failed")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def read(self, addr: int, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        ok = kernel32.ReadProcessMemory(
            self.handle,
            ctypes.c_void_p(addr),
            buf,
            size,
            ctypes.byref(got),
        )
        if not ok or got.value != size:
            raise winerr(f"ReadProcessMemory failed at 0x{addr:X}")
        return buf.raw

    def u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read(addr, 4))[0]

    def i32(self, addr: int) -> int:
        return struct.unpack("<i", self.read(addr, 4))[0]

    def f32(self, addr: int) -> float:
        return struct.unpack("<f", self.read(addr, 4))[0]

    def string(self, addr: int, max_len: int) -> str:
        raw = self.read(addr, max_len)
        raw = raw.split(b"\x00", 1)[0]
        return raw.decode("latin-1", errors="replace")


def safe(call, default=None):
    try:
        return call()
    except Exception:
        return default


class ROProbe:
    def __init__(self, mem: Memory, max_actors: int = 500, address_base: int = 0, base_name: str = "absolute"):
        self.mem = mem
        self.max_actors = max_actors
        self.address_base = address_base
        self.base_name = base_name

    def addr(self, offset: int) -> int:
        return self.address_base + offset

    def manager(self) -> int:
        init = self.mem.u32(self.addr(SINGLETON_BASE) + OFFSET_INIT_FLAG)
        if init != 1:
            return 0
        return self.mem.u32(self.addr(SINGLETON_BASE) + OFFSET_MANAGER_PTR)

    def local_actor(self) -> int:
        mgr = self.manager()
        if not mgr:
            return 0
        actor_list = self.mem.u32(mgr + OFFSET_ACTORLIST)
        if not actor_list:
            return 0
        return self.mem.u32(actor_list + OFFSET_LOCAL_ACTOR)

    def player_world(self) -> tuple[float, float]:
        actor = self.local_actor()
        if not actor:
            return 0.0, 0.0
        return self.mem.f32(actor + ACTOR_WORLD_X), self.mem.f32(actor + ACTOR_WORLD_Y)

    def player_screen(self) -> tuple[int, int]:
        actor = self.local_actor()
        if not actor:
            return 0, 0
        return self.mem.i32(actor + ACTOR_SCREEN_X), self.mem.i32(actor + ACTOR_SCREEN_Y)

    def player(self) -> dict:
        hp = safe(lambda: self.mem.i32(self.addr(LOCAL_HP)), 0)
        sp = safe(lambda: self.mem.i32(self.addr(LOCAL_SP)), 0)
        max_hp = safe(lambda: self.mem.i32(self.addr(LOCAL_MAXHP)), 0)
        max_sp = safe(lambda: self.mem.i32(self.addr(LOCAL_MAXSP)), 0)
        wx, wy = safe(self.player_world, (0.0, 0.0))
        sx, sy = safe(self.player_screen, (0, 0))
        return {
            "gid": safe(lambda: self.mem.u32(self.addr(LOCAL_PLAYER_GID)), 0),
            "aid": safe(lambda: self.mem.u32(self.addr(LOCAL_PLAYER_AID)), 0),
            "hp": hp,
            "max_hp": max_hp,
            "hp_pct": round(hp / max_hp, 4) if max_hp else None,
            "sp": sp,
            "max_sp": max_sp,
            "sp_pct": round(sp / max_sp, 4) if max_sp else None,
            "world": {"x": round(wx, 2), "y": round(wy, 2)},
            "screen": {"x": sx, "y": sy},
        }

    def actors(self) -> list[dict]:
        mgr = self.manager()
        if not mgr:
            return []
        actor_list = self.mem.u32(mgr + OFFSET_ACTORLIST)
        if not actor_list:
            return []
        head_ptr = self.mem.u32(actor_list + OFFSET_LIST_HEAD)
        if not head_ptr:
            return []
        cur_ptr = self.mem.u32(head_ptr)
        local_gid = safe(lambda: self.mem.u32(self.addr(LOCAL_PLAYER_GID)), 0)
        pwx, pwy = safe(self.player_world, (0.0, 0.0))

        actors = []
        visited = set()
        for _ in range(self.max_actors):
            if not cur_ptr or cur_ptr == head_ptr or cur_ptr in visited:
                break
            visited.add(cur_ptr)

            actor_ptr = safe(lambda p=cur_ptr: self.mem.u32(p + 8), 0)
            if actor_ptr:
                gid = safe(lambda p=actor_ptr: self.mem.u32(p + ACTOR_GID), 0)
                if gid and gid != local_gid:
                    typ = safe(lambda p=actor_ptr: self.mem.u32(p + ACTOR_TYPE), 9999)
                    wx = safe(lambda p=actor_ptr: self.mem.f32(p + ACTOR_WORLD_X), 0.0)
                    wy = safe(lambda p=actor_ptr: self.mem.f32(p + ACTOR_WORLD_Y), 0.0)
                    sx = safe(lambda p=actor_ptr: self.mem.i32(p + ACTOR_SCREEN_X), 0)
                    sy = safe(lambda p=actor_ptr: self.mem.i32(p + ACTOR_SCREEN_Y), 0)
                    dist = math.sqrt((wx - pwx) ** 2 + (wy - pwy) ** 2)
                    actors.append({
                        "gid": gid,
                        "type": typ,
                        "type_name": TYPE_NAMES.get(typ, f"unknown_{typ}"),
                        "world": {"x": round(wx, 2), "y": round(wy, 2)},
                        "screen": {"x": sx, "y": sy},
                        "distance": round(dist, 2),
                    })
            cur_ptr = safe(lambda p=cur_ptr: self.mem.u32(p), 0)
        return actors

    def snapshot(self, include: str = "mobs") -> dict:
        actors = self.actors()
        counts = {}
        for actor in actors:
            name = actor["type_name"]
            counts[name] = counts.get(name, 0) + 1

        if include == "mobs":
            out_actors = [a for a in actors if a["type"] == TYPE_MOB]
        elif include == "visible":
            out_actors = [a for a in actors if a["screen"]["x"] > 0 and a["screen"]["y"] > 0]
        elif include == "all":
            out_actors = actors
        else:
            out_actors = []

        out_actors.sort(key=lambda a: a["distance"])
        return {
            "ok": True,
            "ts": time.time(),
            "address_base": {"name": self.base_name, "base": f"0x{self.address_base:X}"},
            "map": safe(lambda: self.mem.string(self.addr(LOCAL_MAP_NAME), 24), ""),
            "manager": f"0x{safe(self.manager, 0):X}",
            "player": self.player(),
            "counts": counts,
            "actors": out_actors,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Ragnarok memory probe")
    parser.add_argument(
        "--process",
        nargs="+",
        default=["Ragnarok.exe", "ragnarok.exe", "RagexeRE.exe", "client.exe"],
        help="process names to search",
    )
    parser.add_argument("--pid", type=int, default=0, help="use a specific PID")
    parser.add_argument("--window-title", default="4th | Gepard", help="fallback window title substring")
    parser.add_argument("--list-processes", action="store_true", help="print process list and exit")
    parser.add_argument("--list-modules", action="store_true", help="print modules for the target process and exit")
    parser.add_argument("--module", default="", help="module name to use with --base module")
    parser.add_argument("--base", choices=["auto", "absolute", "module"], default="auto")
    parser.add_argument("--include", choices=["none", "mobs", "visible", "all"], default="mobs")
    parser.add_argument("--max-actors", type=int, default=500)
    parser.add_argument("--watch", type=float, default=0.0, help="repeat every N seconds")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mem = None
    try:
        if args.list_processes:
            rows = [{"pid": pid, "name": exe} for pid, exe in iter_processes()]
            print(json.dumps(rows, ensure_ascii=False, indent=2 if args.pretty else None))
            return 0

        if args.pid:
            pid, exe = args.pid, f"pid:{args.pid}"
        else:
            try:
                pid, exe = find_process(args.process)
            except RuntimeError:
                pid, exe = find_process_by_window_title(args.window_title)
        mem = Memory(pid)

        if args.list_modules:
            modules = iter_modules(pid)
            print(json.dumps({
                "process": {"pid": pid, "name": exe},
                "modules": modules,
            }, ensure_ascii=False, indent=2 if args.pretty else None))
            return 0

        probes = []
        if args.base in ("auto", "absolute"):
            probes.append(ROProbe(mem, max_actors=args.max_actors, address_base=0, base_name="absolute"))
        if args.base in ("auto", "module"):
            module_base, module_name = choose_module_base(pid, args.module)
            probes.append(ROProbe(
                mem,
                max_actors=args.max_actors,
                address_base=module_base,
                base_name=module_name or "module",
            ))

        probe = probes[0]
        if args.base == "auto" and len(probes) > 1:
            for candidate in probes:
                snap_test = candidate.snapshot(include="none")
                player = snap_test.get("player", {})
                if (
                    snap_test.get("manager") != "0x0"
                    or snap_test.get("map")
                    or player.get("max_hp")
                    or player.get("gid")
                ):
                    probe = candidate
                    break

        while True:
            snap = probe.snapshot(include=args.include)
            snap["process"] = {"pid": pid, "name": exe}
            print(json.dumps(snap, ensure_ascii=False, indent=2 if args.pretty else None), flush=True)
            if args.watch <= 0:
                break
            time.sleep(args.watch)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if mem is not None:
            mem.close()


if __name__ == "__main__":
    raise SystemExit(main())
