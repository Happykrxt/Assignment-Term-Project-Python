# lib_mgmt.py
# Single-file Library Manager (Binary .dat with struct, fixed-length records)
# Files:
#   members.dat (184B/record), books.dat (158B/record), loans.dat (64B/record)
#   report.txt (text report)
# Endianness: Little-Endian

import os, struct, time
from datetime import datetime, timedelta
import shutil, unicodedata

APP_VERSION = "1.0"
MEMBERS_DAT = "members.dat"
BOOKS_DAT   = "books.dat"
LOANS_DAT   = "loans.dat"

# =============== Helpers: filesystem & time ===============
def ensure_file(path: str):
    if not os.path.exists(path):
        with open(path, "wb") as f:
            pass

def now_epoch() -> int:
    return int(time.time())


def fmt_date(ts: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return "-"

# =============== Helpers: fixed-size string ===============
def pack_str(s: str, size: int) -> bytes:
    b = (s or "").encode("utf-8")
    if len(b) > size:
        b = b[:size]
    return b + b"\x00" * (size - len(b))

def unpack_str(b: bytes) -> str:
    return b.split(b"\x00", 1)[0].decode("utf-8", "ignore")

# =============== Helpers: table rendering ===============
def _disp_width(text: str) -> int:
    w = 0
    for ch in str(text):
        if unicodedata.combining(ch):
            continue
        ea = unicodedata.east_asian_width(ch)
        w += 2 if ea in ("W", "F") else 1
    return w

def _truncate_to_width(text: str, width: int) -> str:
    # ตัดข้อความให้พอดีกว้าง width พร้อมเติม ‘…’ ถ้าจำเป็น
    if _disp_width(text) <= width:
        return text
    if width <= 1:
        return "…"[:width]
    out = []
    used = 0
    for ch in str(text):
        cw = 0 if unicodedata.combining(ch) else (2 if unicodedata.east_asian_width(ch) in ("W","F") else 1)
        if used + cw >= width:  # เผื่อที่ให้ …
            break
        out.append(ch)
        used += cw
        if used >= width - 1:
            break
    return "".join(out) + "…"

def _pad(text: str, width: int, align: str = "left") -> str:
    # เติมช่องว่างให้ได้ความกว้างที่ “แสดง” เท่ากับ width
    raw = str(text)
    raw = _truncate_to_width(raw, width)
    gap = width - _disp_width(raw)
    if align == "right":
        return " " * gap + raw
    elif align == "center":
        left = gap // 2
        right = gap - left
        return " " * left + raw + " " * right
    else:
        return raw + " " * gap

def render_table(headers, rows, aligns=None, max_total=None, sep=" │ ", hline_char="─"):
    """
    headers: [str, ...]
    rows:    [[cell,...], ...]
    aligns:  ["left"/"right"/"center", ...] (ถ้าไม่ระบุ default = left)
    max_total: จำกัดความกว้างตารางรวม (ไม่รวม margin ซ้ายขวา) ถ้า None จะใช้ความกว้างจอ
    """
    if aligns is None:
        aligns = ["left"] * len(headers)

    # ความกว้างขั้นต่ำของคอลัมน์ = max(ความกว้างที่แสดงของ header และค่ามากสุดในแถว)
    cols = len(headers)
    widths = [0] * cols
    for i, h in enumerate(headers):
        widths[i] = max(widths[i], _disp_width(h))
    for r in rows:
        for i in range(cols):
            if i < len(r):
                widths[i] = max(widths[i], _disp_width("" if r[i] is None else r[i]))

    # เผื่อช่องคั่น
    sep_w = _disp_width(sep)
    table_content_width = sum(widths) + sep_w * (cols - 1)

    # จำกัดให้พอดีกับจอ
    term_w = shutil.get_terminal_size(fallback=(120, 30)).columns
    limit = max_total or max(60, term_w - 2)   # กันเผื่อเล็กน้อย
    if table_content_width > limit:
        # ตัดคอลัมน์แบบกระจาย: จำกัดคอลัมน์ที่มีแนวโน้มยาว (เช่น title, name)
        # กลยุทธิ์ง่าย ๆ: ใส่เพดานขั้นต่ำ 6 ตัวอักษร สำหรับทุกคอลัมน์ก่อน แล้วจึงลดตามสัดส่วน
        min_col = [max(6, min(30, w)) for w in widths]
        need = table_content_width - limit
        # ลดความกว้างตั้งแต่คอลัมน์ที่กว้างที่สุดลงมาก่อน
        pairs = sorted(list(enumerate(widths)), key=lambda x: x[1], reverse=True)
        for idx, _w in pairs:
            can_reduce = widths[idx] - min_col[idx]
            if can_reduce <= 0:
                continue
            step = min(can_reduce, need)
            widths[idx] -= step
            need -= step
            if need <= 0:
                break
        # ถ้ายังเกินอยู่ก็ยอมหลุดเล็กน้อย

    # ฟังก์ชันวาดเส้น
    def hline(ch=hline_char):
        return ch * (sum(widths) + sep_w * (cols - 1))

    # สร้างบรรทัดหัวตาราง
    header_line = sep.join(_pad(headers[i], widths[i], "center") for i in range(cols))

    # สร้างบรรทัดข้อมูล
    body_lines = []
    for r in rows:
        cells = []
        for i in range(cols):
            val = "" if i >= len(r) or r[i] is None else str(r[i])
            cells.append(_pad(val, widths[i], aligns[i] if i < len(aligns) else "left"))
        body_lines.append(sep.join(cells))

    # ประกอบผลลัพธ์
    top = hline()
    bottom = hline()
    return "\n".join([top, header_line, top] + body_lines + [bottom])


# ==========================================================
#                        Members (184B)
# Layout: <12s 32s 32s 64s 16s 16s B B H Q
#         member_id, first, last, email, phone, major, year(u8), active(u8), reserved(u16), created_at(u64)
MEM_FMT  = "<12s32s32s64s16s16sBBHQ"
MEM_SIZE = struct.calcsize(MEM_FMT)  # 184

class MemberStore:
    def __init__(self, path=MEMBERS_DAT):
        self.path = path
        ensure_file(self.path)

    def pack(self, d: dict) -> bytes:
        return struct.pack(
            MEM_FMT,
            pack_str(d["member_id"], 12),
            pack_str(d["first_name"], 32),
            pack_str(d["last_name"], 32),
            pack_str(d["email"], 64),
            pack_str(d["phone"], 16),
            pack_str(d.get("major",""), 16),
            int(d.get("year",0)) & 0xFF,
            1 if d.get("active", True) else 0,
            0,  # reserved
            int(d.get("created_at", now_epoch()))
        )

    def unpack(self, b: bytes) -> dict:
        (mid, first, last, email, phone, major, year, active, _res, created) = struct.unpack(MEM_FMT, b)
        return {
            "member_id":  unpack_str(mid),
            "first_name": unpack_str(first),
            "last_name":  unpack_str(last),
            "email":      unpack_str(email),
            "phone":      unpack_str(phone),
            "major":      unpack_str(major),
            "year":       int(year),
            "active":     bool(active),
            "created_at": int(created),
        }

    def append(self, d: dict):
        # unique member_id check
        if self.get_by_id(d["member_id"]) is not None:
            raise ValueError(f"Member ID '{d['member_id']}' already exists")
        with open(self.path, "ab") as f:
            f.write(self.pack(d))

    def iter_all(self):
        with open(self.path, "rb") as f:
            while True:
                chunk = f.read(MEM_SIZE)
                if not chunk or len(chunk) < MEM_SIZE:
                    break
                yield self.unpack(chunk)

    def get_by_id(self, member_id: str):
        with open(self.path, "rb") as f:
            idx = 0
            while True:
                chunk = f.read(MEM_SIZE)
                if not chunk or len(chunk) < MEM_SIZE: break
                rec = self.unpack(chunk)
                if rec["member_id"] == member_id:
                    return rec, idx
                idx += 1
        return None

    def update_at(self, index: int, d: dict):
        with open(self.path, "r+b") as f:
            f.seek(index * MEM_SIZE)
            f.write(self.pack(d))

    def soft_delete(self, member_id: str):
        res = self.get_by_id(member_id)
        if not res: raise ValueError("Member not found")
        rec, idx = res
        rec["active"] = False
        self.update_at(idx, rec)

# ==========================================================
#                          Books (158B)
# Layout: <12s 64s 32s 16s H 20s H H Q
#         book_id, title, author, category, year(u16), isbn, total(u16), avail(u16), created_at(u64)
BOOK_FMT  = "<12s64s32s16sH20sHHQ"
BOOK_SIZE = struct.calcsize(BOOK_FMT)  # 158

class BookStore:
    def __init__(self, path=BOOKS_DAT):
        self.path = path
        ensure_file(self.path)

    def pack(self, d: dict) -> bytes:
        return struct.pack(
            BOOK_FMT,
            pack_str(d["book_id"], 12),
            pack_str(d["title"], 64),
            pack_str(d["author"], 32),
            pack_str(d.get("category",""), 16),
            int(d.get("year", 0)) & 0xFFFF,
            pack_str(d.get("isbn",""), 20),
            int(d.get("total_copies",1)) & 0xFFFF,
            int(d.get("available_copies", d.get("total_copies",1))) & 0xFFFF,
            int(d.get("created_at", now_epoch()))
        )

    def unpack(self, b: bytes) -> dict:
        (bid, title, author, category, year, isbn, total, avail, created) = struct.unpack(BOOK_FMT, b)
        return {
            "book_id":          unpack_str(bid),
            "title":            unpack_str(title),
            "author":           unpack_str(author),
            "category":         unpack_str(category),
            "year":             int(year) if year else None,
            "isbn":             unpack_str(isbn),
            "total_copies":     int(total),
            "available_copies": int(avail),
            "created_at":       int(created),
        }

    def append(self, d: dict):
        if self.get_by_id(d["book_id"]) is not None:
            raise ValueError(f"Book ID '{d['book_id']}' already exists")
        with open(self.path, "ab") as f:
            f.write(self.pack(d))

    def iter_all(self):
        with open(self.path, "rb") as f:
            while True:
                chunk = f.read(BOOK_SIZE)
                if not chunk or len(chunk) < BOOK_SIZE: break
                yield self.unpack(chunk)

    def get_by_id(self, book_id: str):
        with open(self.path, "rb") as f:
            idx = 0
            while True:
                chunk = f.read(BOOK_SIZE)
                if not chunk or len(chunk) < BOOK_SIZE: break
                rec = self.unpack(chunk)
                if rec["book_id"] == book_id:
                    return rec, idx
                idx += 1
        return None

    def update_at(self, index: int, d: dict):
        with open(self.path, "r+b") as f:
            f.seek(index * BOOK_SIZE)
            f.write(self.pack(d))

    def delete_hard(self, book_id: str):
        # rewrite without the target (hard delete)
        records = [r for r in self.iter_all() if r["book_id"] != book_id]
        with open(self.path, "wb") as f:
            for r in records:
                f.write(self.pack(r))

# ==========================================================
#                           Loans (64B)
# Layout: <12s 12s 12s Q Q Q B 3x
#         loan_id, member_id, book_id, loan(u64), due(u64), return(u64 or 0), status(u8), pad
# status: 0=borrowed, 1=returned, 2=late
LOAN_FMT  = "<12s12s12sQQQB3x"
LOAN_SIZE = struct.calcsize(LOAN_FMT)  # 64

class LoanStore:
    def __init__(self, path=LOANS_DAT):
        self.path = path
        ensure_file(self.path)

    def pack(self, d: dict) -> bytes:
        return struct.pack(
            LOAN_FMT,
            pack_str(d["loan_id"], 12),
            pack_str(d["member_id"], 12),
            pack_str(d["book_id"], 12),
            int(d.get("loan_date", now_epoch())),
            int(d.get("due_date", now_epoch()+14*86400)),
            int(d.get("return_date", 0)),
            int(d.get("status", 0)) & 0xFF,
        )

    def unpack(self, b: bytes) -> dict:
        (lid, mid, bid, loan_dt, due_dt, ret_dt, status) = struct.unpack(LOAN_FMT, b)
        return {
            "loan_id":    unpack_str(lid),
            "member_id":  unpack_str(mid),
            "book_id":    unpack_str(bid),
            "loan_date":  int(loan_dt),
            "due_date":   int(due_dt),
            "return_date":int(ret_dt),
            "status":     int(status),
        }

    def append(self, d: dict):
        with open(self.path, "ab") as f:
            f.write(self.pack(d))

    def iter_all(self):
        with open(self.path, "rb") as f:
            while True:
                chunk = f.read(LOAN_SIZE)
                if not chunk or len(chunk) < LOAN_SIZE: break
                yield self.unpack(chunk)

    def get_by_id(self, loan_id: str):
        with open(self.path, "rb") as f:
            idx = 0
            while True:
                chunk = f.read(LOAN_SIZE)
                if not chunk or len(chunk) < LOAN_SIZE: break
                rec = self.unpack(chunk)
                if rec["loan_id"] == loan_id:
                    return rec, idx
                idx += 1
        return None

    def update_at(self, index: int, d: dict):
        with open(self.path, "r+b") as f:
            f.seek(index * LOAN_SIZE)
            f.write(self.pack(d))

# ==========================================================
#                  High-level Actions (CRUD + Ops)
# ========== Member ==========
def member_add(mem: MemberStore):
    print("\n=== Member > Add ===")
    mid   = input("Member ID: ").strip()
    first = input("First name: ").strip()
    last  = input("Last name: ").strip()
    email = input("Email: ").strip()
    phone = input("Phone: ").strip()
    major = input("Major (optional): ").strip()
    year  = input("Year (0-255, optional): ").strip()
    d = dict(
        member_id=mid, first_name=first, last_name=last, email=email, phone=phone,
        major=major, year=int(year) if year.isdigit() else 0, active=True, created_at=now_epoch()
    )
    try:
        mem.append(d)
        print("Added.")
    except Exception as e:
        print(f"{e}")

def member_view(mem: MemberStore):
    print("\n=== Member > View ===\n")
    headers = ["MemberID", "Name", "Email", "Phone", "Major", "Year", "Active"]
    aligns  = ["left", "left", "left", "left", "left", "right", "center"]
    rows = []
    for r in mem.iter_all():
        name = (r['first_name'] + " " + r['last_name']).strip()
        rows.append([
            r['member_id'],
            name,
            r['email'],
            r['phone'],
            r['major'],
            r['year'],
            "Yes" if r['active'] else "No",
        ])
    print(render_table(headers, rows, aligns=aligns))

def member_edit(mem: MemberStore):
    print("\n=== Member > Edit ===")
    mid = input("Member ID to edit: ").strip()
    res = mem.get_by_id(mid)
    if not res:
        print("Not found"); return
    rec, idx = res
    print("Leave blank to keep current.")
    def ask(field, label):
        old = rec.get(field, "")
        return input(f"{label} [{old}]: ").strip() or old
    rec["first_name"] = ask("first_name","First name")
    rec["last_name"]  = ask("last_name","Last name")
    rec["email"]      = ask("email","Email")
    rec["phone"]      = ask("phone","Phone")
    rec["major"]      = ask("major","Major")
    y = input(f"Year [{rec.get('year',0)}]: ").strip()
    rec["year"] = int(y) if y.isdigit() else rec.get("year",0)
    a = input(f"Active true/false [{rec.get('active',True)}]: ").strip().lower()
    if a in ("true","false"):
        rec["active"] = (a=="true")
    mem.update_at(idx, rec)
    print("Updated.")

def member_delete(mem: MemberStore):
    print("\n=== Member > Delete (soft) ===")
    mid = input("Member ID to deactivate: ").strip()
    try:
        mem.soft_delete(mid)
        print("Deactivated (active = False).")
    except Exception as e:
        print(f"{e}")

# ========== Book ==========
def book_add(bk: BookStore):
    print("\n=== Book > Add ===")
    bid   = input("Book ID: ").strip()
    title = input("Title: ").strip()
    author= input("Author: ").strip()
    category = input("Category: ").strip()
    year  = input("Year: ").strip()
    isbn  = input("ISBN: ").strip()
    copies= input("Total copies: ").strip()
    d = dict(
        book_id=bid, title=title, author=author, category=category,
        year=int(year) if year.isdigit() else 0,
        isbn=isbn, total_copies=int(copies) if copies.isdigit() else 1,
        available_copies=int(copies) if copies.isdigit() else 1, created_at=now_epoch()
    )
    try:
        bk.append(d); print("Added.")
    except Exception as e:
        print(f"{e}")

def book_view(bk: BookStore):
    print("\n=== Book > View ===\n")
    headers = ["BookID", "Title", "Author", "Year", "Copies", "Avail"]
    aligns  = ["left", "left", "left", "right", "right", "right"]
    rows = []
    for r in bk.iter_all():
        rows.append([
            r['book_id'],
            r['title'],
            r['author'],
            r['year'] if r['year'] else "",
            r['total_copies'],
            r['available_copies'],
        ])
    print(render_table(headers, rows, aligns=aligns))
def book_edit(bk: BookStore):
    print("\n=== Book > Edit ===")
    bid = input("Book ID to edit: ").strip()
    res = bk.get_by_id(bid)
    if not res: print("Not found"); return
    rec, idx = res
    print("Leave blank to keep current.")
    def ask(field, label):
        old = rec.get(field, "")
        return input(f"{label} [{old}]: ").strip() or old
    rec["title"]  = ask("title","Title")
    rec["author"] = ask("author","Author")
    rec["category"] = ask("category","Category")
    y = input(f"Year [{rec.get('year',0)}]: ").strip()
    if y.isdigit(): rec["year"] = int(y)
    rec["isbn"]   = ask("isbn","ISBN")
    c = input(f"Total copies [{rec.get('total_copies',1)}]: ").strip()
    if c.isdigit():
        new_total = int(c)
        diff = new_total - int(rec.get("total_copies",0))
        rec["total_copies"] = new_total
        rec["available_copies"] = max(0, int(rec.get("available_copies",0)) + diff)
    bk.update_at(idx, rec); print("Updated.")

def book_delete(bk: BookStore):
    print("\n=== Book > Delete (hard) ===")
    bid = input("Book ID to delete: ").strip()
    try:
        bk.delete_hard(bid); print("Deleted.")
    except Exception as e:
        print(f"{e}")

# ========== Loan ==========
def loan_view(ln: LoanStore, mem: MemberStore = None, bk: BookStore = None):
    """
    Loan View (เวอร์ชันปรับปรุง):
    - หัว/ท้ายตารางด้วย render_table
    - แสดงชื่อสมาชิกแทน member_id, Status ไปท้ายสุด
    - แสดงเฉพาะ 'วันที่' (YYYY-MM-DD)
    - สรุปท้ายตาราง:
        * Borrowed Today: สรุปสมาชิกที่ยืมวันนี้ รวมชื่อหนังสือของรายการที่ 'ยืมวันเดียวกัน' และ (ถ้ามี) 'คืนวันเดียวกัน'
        * Returned Today: สรุปสมาชิกที่คืนวันนี้ รวมชื่อหนังสือของรายการที่ 'ยืมวันเดียวกัน' และ 'คืนวันเดียวกัน'
        * Overdue: นับจำนวนสมาชิกที่ยัง Borrowed และเลยกำหนดคืน (unique)
    - ในการรวม (group) จะเลือก loan_id ตัวแทนของกลุ่มเป็นค่าที่น้อยสุด (lexicographical min)
    """
    import time
    from datetime import datetime

    mem = mem or MemberStore(MEMBERS_DAT)
    bk  = bk  or BookStore(BOOKS_DAT)

    mem_map  = {m["member_id"]: m for m in mem.iter_all()}
    book_map = {b["book_id"]: b for b in bk.iter_all()}
    loans = list(ln.iter_all())

    # ===== ตารางหลัก =====
    headers = ["LoanID", "Member Name", "BookID", "Title", "LoanDate", "DueDate", "ReturnDate", "Status"]
    aligns  = ["left", "left", "left", "left", "left", "left", "left", "left"]
    rows = []

    def status_text(s):
        return {0: "borrowed", 1: "returned", 2: "late"}.get(s, "?")

    today = datetime.now().date()
    borrowers_today_set = set()  # สมาชิกที่ 'ยืม' วันนี้ (unique member_id)
    returns_today_set   = set()  # สมาชิกที่ 'คืน' วันนี้ (unique member_id)
    overdue_people_set  = set()  # สมาชิกที่ 'ยังยืม' และ 'เกินกำหนด' (unique member_id)

    # เก็บข้อมูลที่ใช้สำหรับสรุปแบบ grouping
    # key สำหรับ 'Borrowed Today' = (member_id, loan_date_date, return_date_date or None)
    groups_borrow_today = {}
    # key สำหรับ 'Returned Today' = (member_id, loan_date_date, return_date_date)
    groups_return_today = {}

    for l in loans:
        m = mem_map.get(l["member_id"], {})
        b = book_map.get(l["book_id"], {})

        member_name = ((m.get("first_name","") + " " + m.get("last_name","")).strip()) or "-"
        title = b.get("title", "-")

        rows.append([
            l["loan_id"],
            member_name,
            l["book_id"],
            title,
            fmt_date(l["loan_date"]),
            fmt_date(l["due_date"]),
            "-" if l["return_date"] == 0 else fmt_date(l["return_date"]),
            status_text(l["status"]),
        ])

        # ===== นับชุด "วันนี้" =====
        loan_d = datetime.fromtimestamp(l["loan_date"]).date() if l["loan_date"] else None
        ret_d  = (datetime.fromtimestamp(l["return_date"]).date()
                  if l["return_date"] else None)

        # ผู้ที่ 'ยืม' วันนี้
        if loan_d == today:
            borrowers_today_set.add(l["member_id"])
            # รวมตาม (member_id, loan_d, ret_d|None) เพื่อทำกลุ่ม "ถ้ายืมวันเดียวกัน และถ้าคืนวันเดียวกัน"
            key_b = (l["member_id"], loan_d, ret_d if ret_d == today else None)
            g = groups_borrow_today.setdefault(key_b, {"loan_ids": [], "titles": set()})
            g["loan_ids"].append(l["loan_id"])
            if title:
                g["titles"].add(title)

        # ผู้ที่ 'คืน' วันนี้
        if ret_d == today:
            returns_today_set.add(l["member_id"])
            # รวมตาม (member_id, loan_d, ret_d) โดยต้องคืนวันนี้แน่ ๆ
            key_r = (l["member_id"], loan_d, ret_d)
            g = groups_return_today.setdefault(key_r, {"loan_ids": [], "titles": set()})
            g["loan_ids"].append(l["loan_id"])
            if title:
                g["titles"].add(title)

        # Overdue: ยังยืมอยู่ และเกินกำหนด ณ ตอนนี้
        if l["status"] == 0 and l["due_date"] < int(time.time()):
            overdue_people_set.add(l["member_id"])

    print("\n=== Loan > View ===\n")
    print(render_table(headers, rows, aligns=aligns))

    # ====== ส่วนสรุปแบบอ่านง่าย ======
    # ตัวช่วยแสดงชื่อสมาชิกจาก member_id
    def member_display(mid: str) -> str:
        mm = mem_map.get(mid, {})
        return ((mm.get("first_name","") + " " + mm.get("last_name","")).strip()) or mid or "-"

    # ---- สรุป: Borrowed Today ----
    if groups_borrow_today:
        print("Borrowed Today")
        # เรียงตามชื่อสมาชิกเพื่ออ่านง่าย
        for key in sorted(groups_borrow_today.keys(), key=lambda k: member_display(k[0])):
            mid, loan_d, ret_d = key
            g = groups_borrow_today[key]
            rep_loan_id = min(g["loan_ids"])  # ใช้ loan_id ตัวแทนที่เล็กสุดในกลุ่ม
            titles = ", ".join(sorted(g["titles"])) if g["titles"] else "-"
            md = member_display(mid)
            # กรณีมีคืนวันนี้ (ret_d == today) เราจะโชว์เป็น “(borrow & return today)”
            note = " (borrow & return today)" if ret_d is not None else ""
            print(f"- {md}  | LoanID: {rep_loan_id} | {titles}{note}")
        print()

    # ---- สรุป: Returned Today ----
    if groups_return_today:
        print("Returned Today")
        for key in sorted(groups_return_today.keys(), key=lambda k: member_display(k[0])):
            mid, loan_d, ret_d = key
            g = groups_return_today[key]
            rep_loan_id = min(g["loan_ids"])
            titles = ", ".join(sorted(g["titles"])) if g["titles"] else "-"
            md = member_display(mid)
            # ถ้าทั้งยืมและคืนวันนี้จริง ๆ ก็ถือว่าเป็น same-day pair
            note = " (same-day)" if (loan_d == today and ret_d == today) else ""
            print(f"- {md}  | LoanID: {rep_loan_id} | {titles}{note}")
        print()

    # ---- Count Summary line ----
    print(f"Summary today -> Borrowers: {len(borrowers_today_set)}  |  Returns: {len(returns_today_set)}  |  Overdue: {len(overdue_people_set)}\n")


def loan_borrow(ln: LoanStore, mem: MemberStore, bk: BookStore):
    print("\n=== Loan > Borrow ===")
    mid  = input("Member ID: ").strip()
    bid  = input("Book ID: ").strip()
    days = input("Days (default 14): ").strip()
    days_v = int(days) if days.isdigit() else 14

    # validations
    mres = mem.get_by_id(mid)
    if not mres or not mres[0]["active"]:
        print("Member not found or inactive"); return
    bres = bk.get_by_id(bid)
    if not bres:
        print("Book not found"); return
    book, bidx = bres
    if int(book["available_copies"]) <= 0:
        print("No available copies"); return

    # update book avail
    book["available_copies"] -= 1
    bk.update_at(bidx, book)

    loan = {
        "loan_id": f"LN{int(time.time())}",
        "member_id": mid,
        "book_id": bid,
        "loan_date": now_epoch(),
        "due_date": now_epoch() + days_v*86400,
        "return_date": 0,
        "status": 0,  # borrowed
    }
    ln.append(loan)
    print("Borrowed.")

def loan_return(ln: LoanStore, bk: BookStore):
    print("\n=== Loan > Return ===")
    lid = input("Loan ID: ").strip()
    res = ln.get_by_id(lid)
    if not res: print("Loan not found"); return
    rec, idx = res
    if rec["status"] == 1:
        print("ℹ️ Already returned"); return
    # set return
    rec["return_date"] = now_epoch()
    rec["status"] = 2 if rec["return_date"] > rec["due_date"] else 1
    ln.update_at(idx, rec)
    # give book back
    bres = bk.get_by_id(rec["book_id"])
    if bres:
        book, bidx = bres
        book["available_copies"] += 1
        bk.update_at(bidx, book)
    print("Returned.")

# ==========================================================
#                          Report
def build_report(mem: MemberStore, bk: BookStore, ln: LoanStore,
                 include_members=True, include_books=True, include_loans=True,
                 active_members_only=False, loans_scope="all",
                 loans_from="", loans_to="") -> str:
    """Summary Report แบบข้อความ — แสดงเฉพาะ 'วันที่' ในส่วน Loans และวาง Status ไว้คอลัมน์สุดท้าย"""

    def mkline(width: int, ch: str = "-") -> str:
        return ch * width

    now = datetime.now()
    header_lines = [
        "Library System — Summary Report",
        f"Generated At : {now.strftime('%Y-%m-%d')}",
        f"App Version  : {APP_VERSION}",
        "Endianness   : Little-Endian",
        "Encoding     : UTF-8 (fixed-length)",
    ]
    out = "\n".join(header_lines)

    # ---------------- Members ----------------
    members = list(mem.iter_all())
    if active_members_only:
        members = [m for m in members if m.get("active", True)]

    if include_members:
        out += "\n\nMembers\n"
        head_m = f"{'MemberID':<12} {'Name':<26} {'Email':<28} {'Phone':<14} {'Major':<10} {'Year':<4} {'Active':<6}"
        line_m = mkline(len(head_m))
        out += line_m + "\n" + head_m + "\n" + line_m + "\n"
        for m in members:
            name = (m['first_name'] + " " + m['last_name']).strip()
            out += (f"{m['member_id']:<12} {name:<26} {m['email']:<28} {m['phone']:<14} "
                    f"{m['major']:<10} {m['year']:<4} {('Yes' if m['active'] else 'No'):<6}\n")
        out += line_m

    # ---------------- Books ----------------
    books = list(bk.iter_all())
    if include_books:
        out += "\n\nBooks\n"
        head_b = f"{'BookID':<10} {'Title':<24} {'Author':<18} {'Year':<6} {'Copies':<7} {'Avail':<7}"
        line_b = mkline(len(head_b))
        out += line_b + "\n" + head_b + "\n" + line_b + "\n"
        for b in books:
            out += (f"{b['book_id']:<10} {b['title']:<24} {b['author']:<18} "
                    f"{str(b['year'] or ''):<6} {b['total_copies']:<7} {b['available_copies']:<7}\n")
        out += line_b

    # ---------------- Loans (with joins) ----------------
    loans = list(ln.iter_all())

    # scope filter
    if loans_scope == "active":
        loans = [l for l in loans if l["status"] == 0]
    elif loans_scope == "returned":
        loans = [l for l in loans if l["status"] == 1]
    elif loans_scope == "overdue":
        loans = [l for l in loans if l["status"] == 0 and l["due_date"] < now_epoch()]

    # date-range filter (by loan_date, input ISO)
    def parse_iso(s):
        try:
            return int(datetime.fromisoformat(s).timestamp())
        except Exception:
            return None
    from_ts = parse_iso(loans_from) if loans_from else None
    to_ts   = parse_iso(loans_to)   if loans_to   else None
    if from_ts is not None:
        loans = [l for l in loans if l["loan_date"] >= from_ts]
    if to_ts is not None:
        loans = [l for l in loans if l["loan_date"] <= to_ts]

    if include_loans:
        out += "\n\nLoans\n"
        # เปลี่ยนหัวคอลัมน์: ใช้วันที่แบบ 10 ตัวอักษร และย้าย Status ไปท้ายสุด
        head_l = (
            f"{'LoanID':<14} {'MemberID':<12} {'Member Name':<24} "
            f"{'BookID':<10} {'Title':<22} {'Loan':<10} {'Due':<10} {'Return':<10} {'Status':<8}"
        )
        line_l = mkline(len(head_l))
        out += line_l + "\n" + head_l + "\n" + line_l + "\n"

        mem_map  = {m["member_id"]: m for m in mem.iter_all()}
        book_map = {b["book_id"]: b for b in bk.iter_all()}

        def status_text(s):
            return {0: "borrowed", 1: "returned", 2: "late"}.get(s, "?")

        for l in loans:
            m = mem_map.get(l["member_id"], {})
            b = book_map.get(l["book_id"], {})
            mname = ((m.get("first_name","") + " " + m.get("last_name","")).strip()) or "-"
            out += (
                f"{l['loan_id']:<14} {l['member_id']:<12} {mname:<24} {l['book_id']:<10} "
                f"{b.get('title','-'):<22} {fmt_date(l['loan_date']):<10} {fmt_date(l['due_date']):<10} "
                f"{('-' if l['return_date']==0 else fmt_date(l['return_date'])):<10} {status_text(l['status']):<8}\n"
            )
        out += line_l

    # ---------------- Summary ----------------
    active_m = [m for m in mem.iter_all() if m.get("active", True)]
    total_titles = len(books)
    total_copies = sum(b["total_copies"] for b in books)
    avail_copies = sum(b["available_copies"] for b in books)
    active_loans = [l for l in ln.iter_all() if l["status"] == 0]
    overdue_cnt  = sum(1 for l in active_loans if l["due_date"] < now_epoch())

    out += "\n\nSummary\n"
    out += f"- Members (all/active): {len(list(mem.iter_all()))} / {len(active_m)}\n"
    out += f"- Books (titles):       {total_titles}\n"
    out += f"- Copies (total/avail): {total_copies} / {avail_copies}\n"
    out += f"- Loans (active):       {len(active_loans)}\n"
    out += f"- Overdue:              {overdue_cnt}\n"
    out += mkline(60) + "\n"
    return out

def report_menu(mem: MemberStore, bk: BookStore, ln: LoanStore):
    print("\n=== Report (with filters) ===")
    inc_m = (input("Include Members? (Y/n): ").strip().lower() or "y") != "n"
    inc_b = (input("Include Books?   (Y/n): ").strip().lower() or "y") != "n"
    inc_l = (input("Include Loans?   (Y/n): ").strip().lower() or "y") != "n"
    only_active_m = input("Members: active only? (y/N): ").strip().lower() == "y"
    print("Loans scope: 1) all  2) active  3) overdue  4) returned")
    scope = {"1":"all","2":"active","3":"overdue","4":"returned"}.get(input("Choose (1-4) [1]: ").strip() or "1","all")
    lf = input("Loans from (ISO, blank=none): ").strip()
    lt = input("Loans to   (ISO, blank=none): ").strip()

    rep = build_report(mem, bk, ln, inc_m, inc_b, inc_l, only_active_m, scope, lf, lt)
    print("\n"+rep)
    if (input("Save to file? (y/N): ").strip().lower() == "y"):
        name = input("Filename [report.txt]: ").strip() or "report.txt"
        with open(name, "w", encoding="utf-8") as f:
            f.write(rep)
        print(f"Saved: {name}")

# ==========================================================
#                           Menus
def pause():
    input("\nPress Enter to continue...")

def menu_member(mem: MemberStore):
    while True:
        print("\n==== Member Menu ====")
        print("1) Add")
        print("2) View")
        print("3) Edit")
        print("4) Delete (soft: active=False)")
        print("0) Back")
        c = input("Choose: ").strip()
        if   c=="1": member_add(mem); pause()
        elif c=="2": member_view(mem); pause()
        elif c=="3": member_edit(mem); pause()
        elif c=="4": member_delete(mem); pause()
        elif c=="0": break
        else: print("Invalid option")

def menu_book(bk: BookStore):
    while True:
        print("\n==== Book Menu ====")
        print("1) Add")
        print("2) View")
        print("3) Edit")
        print("4) Delete (hard)")
        print("0) Back")
        c = input("Choose: ").strip()
        if   c=="1": book_add(bk); pause()
        elif c=="2": book_view(bk); pause()
        elif c=="3": book_edit(bk); pause()
        elif c=="4": book_delete(bk); pause()
        elif c=="0": break
        else: print("Invalid option")

def menu_loan(ln: LoanStore, mem: MemberStore, bk: BookStore):
    while True:
        print("\n==== Loan Menu ====")
        print("1) Borrow")
        print("2) Return")
        print("3) View")
        print("0) Back")
        c = input("Choose: ").strip()
        if   c=="1": loan_borrow(ln, mem, bk); pause()
        elif c=="2": loan_return(ln, bk); pause()
        elif c=="3": loan_view(ln); pause()
        elif c=="0": break
        else: print("Invalid option")

# ==========================================================
#                            Main
def main():
    # Ensure all .dat files exist upfront
    for p in (MEMBERS_DAT, BOOKS_DAT, LOANS_DAT):
        ensure_file(p)

    mem = MemberStore(MEMBERS_DAT)
    bk  = BookStore(BOOKS_DAT)
    ln  = LoanStore(LOANS_DAT)

    while True:
        print("\n===== Main Menu =====")
        print("1) Member")
        print("2) Book")
        print("3) Loan")
        print("4) Report")
        print("0) Exit")
        cmd = input("Choose: ").strip()
        if   cmd=="1": menu_member(mem)
        elif cmd=="2": menu_book(bk)
        elif cmd=="3": menu_loan(ln, mem, bk)
        elif cmd=="4": report_menu(mem, bk, ln)
        elif cmd=="0":
            print("Bye!")
            break
        else:
            print("Invalid option")

if __name__ == "__main__":
    main()
