"""
lib_mgmt.py — Single-file Library Manager (Members / Books / Loans / Report)
- เก็บข้อมูลเป็นไฟล์ .txt แบบ JSON Lines (1 บรรทัด = 1 record)
- ใช้เฉพาะ Standard Library ของ Python
- เมนู:
    Main -> Member (Add/Delete/View/Edit)
         -> Book   (Add/Delete/View/Edit)
         -> Loan   (Borrow/Return/View)
         -> Report (Generate with filters, print or save .txt)
"""

import json
import os
from datetime import datetime, timedelta

MEMBERS_FILE = "members.txt"
BOOKS_FILE   = "books.txt"
LOANS_FILE   = "loans.txt"
APP_VERSION  = "1.0"

# ========================= Utilities =========================
def _ensure_file(path: str):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            pass

def _read_jsonl(path: str):
    _ensure_file(path)
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                items.append(json.loads(s))
            except json.JSONDecodeError:
                # ข้ามบรรทัดที่เสีย
                continue
    return items

def _write_jsonl(path: str, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def _now_iso():
    return datetime.now().isoformat(timespec="seconds")

def _parse_iso(s: str):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

# ========================= Members =========================
class MemberManager:
    def __init__(self, filepath=MEMBERS_FILE):
        self.filepath = filepath
        _ensure_file(self.filepath)

    def add_member(self, student_id, first_name, last_name, email, phone, major="", year=""):
        members = self.list_members()
        if any(m.get("student_id") == student_id for m in members):
            raise ValueError(f"Student ID '{student_id}' มีอยู่แล้ว")

        rec = {
            "student_id": student_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "major": major,
            "year": year,
            "active": True,
            "created_at": _now_iso(),
        }
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def delete_member(self, student_id):
        members = self.list_members()
        new_members = [m for m in members if m.get("student_id") != student_id]
        if len(new_members) == len(members):
            raise ValueError(f"ไม่พบ Student ID '{student_id}'")
        _write_jsonl(self.filepath, new_members)

    def edit_member(self, student_id, **updates):
        members = self.list_members()
        found = False
        for m in members:
            if m.get("student_id") == student_id:
                for k, v in updates.items():
                    if v is None or v == "":
                        continue
                    m[k] = v
                found = True
                break
        if not found:
            raise ValueError(f"ไม่พบ Student ID '{student_id}'")
        _write_jsonl(self.filepath, members)

    def list_members(self):
        return _read_jsonl(self.filepath)

    def get_member(self, student_id):
        for m in self.list_members():
            if m.get("student_id") == student_id:
                return m
        return None

# ========================= Books =========================
class BookManager:
    def __init__(self, filepath=BOOKS_FILE):
        self.filepath = filepath
        _ensure_file(self.filepath)

    def add_book(self, book_id, title, author, category="", year=None, isbn="", copies=1):
        books = self.list_books()
        if any(b.get("book_id") == book_id for b in books):
            raise ValueError(f"Book ID '{book_id}' มีอยู่แล้ว")
        copies = int(copies) if copies else 1

        rec = {
            "book_id": book_id,
            "title": title,
            "author": author,
            "category": category,
            "year": int(year) if (isinstance(year, str) and year.strip().isdigit()) else (year if year else None),
            "isbn": isbn,
            "total_copies": copies,
            "available_copies": copies,
            "created_at": _now_iso(),
        }
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def delete_book(self, book_id):
        books = self.list_books()
        new_books = [b for b in books if b.get("book_id") != book_id]
        if len(new_books) == len(books):
            raise ValueError(f"ไม่พบ Book ID '{book_id}'")
        _write_jsonl(self.filepath, new_books)

    def edit_book(self, book_id, **updates):
        books = self.list_books()
        found = False
        for b in books:
            if b.get("book_id") == book_id:
                for k, v in updates.items():
                    if v is None or v == "":
                        continue
                    if k in ("total_copies", "available_copies", "year") and isinstance(v, str) and v.isdigit():
                        v = int(v)
                    b[k] = v
                found = True
                break
        if not found:
            raise ValueError(f"ไม่พบ Book ID '{book_id}'")
        _write_jsonl(self.filepath, books)

    def list_books(self):
        return _read_jsonl(self.filepath)

    def get_book(self, book_id):
        for b in self.list_books():
            if b.get("book_id") == book_id:
                return b
        return None

    def _set_available(self, book_id, new_available):
        books = self.list_books()
        for b in books:
            if b.get("book_id") == book_id:
                b["available_copies"] = int(new_available)
                _write_jsonl(self.filepath, books)
                return
        raise ValueError("book not found")

# ========================= Loans =========================
class LoanManager:
    """
    จัดการยืม-คืนใน loans.txt
    status: borrowed | returned | late
    """
    def __init__(self, filepath=LOANS_FILE, mem_mgr: MemberManager=None, book_mgr: BookManager=None):
        self.filepath = filepath
        _ensure_file(self.filepath)
        self.mem_mgr = mem_mgr
        self.book_mgr = book_mgr

    def list_loans(self):
        return _read_jsonl(self.filepath)

    def list_active_loans(self):
        return [x for x in self.list_loans() if x.get("status") == "borrowed"]

    def borrow(self, student_id, book_id, days=14, remarks=""):
        # ตรวจสมาชิก
        m = self.mem_mgr.get_member(student_id) if self.mem_mgr else None
        if not m or not m.get("active", True):
            raise ValueError("ไม่พบสมาชิกหรือสถานะไม่พร้อมใช้งาน")

        # ตรวจหนังสือ
        b = self.book_mgr.get_book(book_id) if self.book_mgr else None
        if not b:
            raise ValueError("ไม่พบหนังสือ")
        if int(b.get("available_copies", 0)) <= 0:
            raise ValueError("จำนวนหนังสือคงเหลือไม่พอให้ยืม")

        # ลด available_copies
        self.book_mgr._set_available(book_id, int(b["available_copies"]) - 1)

        loan_id = f"LN{int(datetime.now().timestamp())}"
        loan = {
            "loan_id": loan_id,
            "student_id": student_id,
            "book_id": book_id,
            "loan_date": _now_iso(),
            "due_date": (datetime.now() + timedelta(days=int(days))).isoformat(timespec="seconds"),
            "return_date": None,
            "status": "borrowed",
            "remarks": remarks or "",
        }
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(loan, ensure_ascii=False) + "\n")
        return loan

    def return_book(self, loan_id):
        loans = self.list_loans()
        found = None
        for l in loans:
            if l.get("loan_id") == loan_id:
                found = l
                break
        if not found:
            raise ValueError(f"ไม่พบรายการยืม '{loan_id}'")

        if found.get("status") == "returned":
            return found  # คืนแล้วก่อนหน้า

        # ตีคืน
        found["return_date"] = _now_iso()
        try:
            due_dt = datetime.fromisoformat(found["due_date"])
            ret_dt = datetime.fromisoformat(found["return_date"])
            found["status"] = "late" if ret_dt > due_dt else "returned"
        except Exception:
            found["status"] = "returned"

        # เซฟ loans
        _write_jsonl(self.filepath, loans)

        # เพิ่ม available_copies คืนให้หนังสือ
        b = self.book_mgr.get_book(found["book_id"])
        if b:
            self.book_mgr._set_available(b["book_id"], int(b.get("available_copies", 0)) + 1)

        return found

# ========================= Report =========================
class ReportManager:
    """
    รวมข้อมูล Members + Books + Loans แล้วพิมพ์รายงานแบบ ASCII
    รองรับตัวกรอง (filters) และบันทึกไฟล์ได้
    """
    def __init__(self, mem_mgr: MemberManager, book_mgr: BookManager, loan_mgr: LoanManager):
        self.mem_mgr = mem_mgr
        self.book_mgr = book_mgr
        self.loan_mgr = loan_mgr

    # ---- table helpers ----
    def _line(self, width=118, ch="-"):
        return ch * width

    def _fmt_row(self, cols, widths):
        out = []
        for i, w in enumerate(widths):
            val = str(cols[i]) if i < len(cols) else ""
            if len(val) > w:
                val = val[: w-1] + "…"  # truncate
            out.append(f"{val:<{w}}")
        return " | ".join(out)

    def _section(self, title):
        return f"\n{title}\n"

    def build(self, filters: dict) -> str:
        """
        filters keys:
          include_members: bool
          include_books:   bool
          include_loans:   bool
          active_members_only: bool
          loans_scope: 'all' | 'active' | 'overdue' | 'returned'
          loans_from: ISO string or ''
          loans_to:   ISO string or ''
        """
        now = datetime.now()
        header = []
        header.append("Library System — Summary Report")
        header.append(f"Generated At : {now.strftime('%Y-%m-%d %H:%M:%S')} (+{now.astimezone().utcoffset()})")
        header.append(f"App Version  : {APP_VERSION}")
        header.append("Encoding     : UTF-8")
        report = "\n".join(header) + "\n" + self._line() + "\n"

        # -------- members table --------
        members = self.mem_mgr.list_members()
        if filters.get("active_members_only", False):
            members = [m for m in members if m.get("active", True)]

        if filters.get("include_members", True):
            report += self._section("Members (filtered)") + self._line() + "\n"
            widths = [10, 22, 28, 12, 8, 4, 6]
            head = ["Student", "Name", "Email", "Phone", "Major", "Year", "Active"]
            report += self._fmt_row(head, widths) + "\n" + self._line() + "\n"
            for m in members:
                name = f"{m.get('first_name','')} {m.get('last_name','')}".strip()
                row = [
                    m.get("student_id",""),
                    name,
                    m.get("email",""),
                    m.get("phone",""),
                    m.get("major",""),
                    m.get("year",""),
                    "Yes" if m.get("active",True) else "No",
                ]
                report += self._fmt_row(row, widths) + "\n"
            report += self._line() + "\n"

        # -------- books table --------
        books = self.book_mgr.list_books()
        if filters.get("include_books", True):
            report += self._section("Books") + self._line() + "\n"
            widths = [8, 24, 18, 6, 7, 7]
            head = ["BookID", "Title", "Author", "Year", "Copies", "Avail"]
            report += self._fmt_row(head, widths) + "\n" + self._line() + "\n"
            for b in books:
                row = [
                    b.get("book_id",""),
                    b.get("title",""),
                    b.get("author",""),
                    str(b.get("year","")),
                    b.get("total_copies",0),
                    b.get("available_copies",0),
                ]
                report += self._fmt_row(row, widths) + "\n"
            report += self._line() + "\n"

        # -------- loans table (join) --------
        loans = self.loan_mgr.list_loans()
        scope = filters.get("loans_scope", "all")
        if scope == "active":
            loans = [l for l in loans if l.get("status") == "borrowed"]
        elif scope == "returned":
            loans = [l for l in loans if l.get("status") == "returned"]
        elif scope == "overdue":
            def _is_overdue(l):
                if l.get("status") != "borrowed": return False
                due = _parse_iso(l.get("due_date",""))
                return bool(due and due < datetime.now())
            loans = [l for l in loans if _is_overdue(l)]

        # date range filter on loan_date
        d_from = _parse_iso(filters.get("loans_from","") or "")
        d_to   = _parse_iso(filters.get("loans_to","") or "")
        if d_from:
            loans = [l for l in loans if _parse_iso(l.get("loan_date","")) and _parse_iso(l.get("loan_date","")) >= d_from]
        if d_to:
            loans = [l for l in loans if _parse_iso(l.get("loan_date","")) and _parse_iso(l.get("loan_date","")) <= d_to]

        if filters.get("include_loans", True):
            report += self._section("Loans (joined)") + self._line() + "\n"
            widths = [12, 8, 22, 8, 20, 8, 19, 19, 19]
            head = ["LoanID", "StuID", "Student Name", "BookID", "Title", "Status", "LoanDate", "DueDate", "Return"]
            report += self._fmt_row(head, widths) + "\n" + self._line() + "\n"
            # build lookup
            mem_by_id = {m.get("student_id"): m for m in self.mem_mgr.list_members()}
            book_by_id = {b.get("book_id"): b for b in self.book_mgr.list_books()}
            for l in loans:
                m = mem_by_id.get(l.get("student_id"), {})
                b = book_by_id.get(l.get("book_id"), {})
                name = f"{m.get('first_name','')} {m.get('last_name','')}".strip()
                row = [
                    l.get("loan_id",""),
                    l.get("student_id",""),
                    name,
                    l.get("book_id",""),
                    b.get("title",""),
                    l.get("status",""),
                    l.get("loan_date",""),
                    l.get("due_date",""),
                    l.get("return_date",""),
                ]
                report += self._fmt_row(row, widths) + "\n"
            report += self._line() + "\n"

        # -------- Summary --------
        active_members = [m for m in self.mem_mgr.list_members() if m.get("active", True)]
        total_books = len(books)
        total_copies = sum(int(b.get("total_copies",0)) for b in books)
        avail_copies = sum(int(b.get("available_copies",0)) for b in books)
        loan_active = [l for l in self.loan_mgr.list_loans() if l.get("status") == "borrowed"]
        overdue_cnt = 0
        for l in loan_active:
            due = _parse_iso(l.get("due_date",""))
            if due and due < datetime.now():
                overdue_cnt += 1

        report += self._section("Summary")
        report += f"- Members (all/active): {len(self.mem_mgr.list_members())} / {len(active_members)}\n"
        report += f"- Books (titles):       {total_books}\n"
        report += f"- Copies (total/avail): {total_copies} / {avail_copies}\n"
        report += f"- Loans (active):       {len(loan_active)}\n"
        report += f"- Overdue:              {overdue_cnt}\n"
        report += self._line() + "\n"

        return report

# ========================= Menu Helpers =========================
def _pause():
    input("\nกด Enter เพื่อกลับเมนู...")

def _input_nonempty(prompt: str) -> str:
    while True:
        val = input(prompt).strip()
        if val:
            return val
        print("กรุณากรอกข้อมูลให้ครบ")

# ========================= Member Menus =========================
def menu_member_add(mgr: MemberManager):
    print("\n=== Member > Add ===")
    sid   = _input_nonempty("Student ID: ")
    first = _input_nonempty("First name: ")
    last  = _input_nonempty("Last name: ")
    email = _input_nonempty("Email: ")
    phone = _input_nonempty("Phone: ")
    major = input("Major (optional): ").strip()
    year  = input("Year (optional): ").strip()
    try:
        rec = mgr.add_member(sid, first, last, email, phone, major, year)
        print(f"\n✅ Added: {rec['student_id']} - {rec['first_name']} {rec['last_name']}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    _pause()

def menu_member_view(mgr: MemberManager):
    print("\n=== Member > View ===\n")
    members = mgr.list_members()
    if not members:
        print("No members yet.")
    else:
        print(f"{'StudentID':<12} {'Name':<26} {'Email':<30} {'Phone':<14} {'Major':<10} {'Year':<6} {'Active':<6}")
        print("-" * 112)
        for m in members:
            name = f"{m.get('first_name','')} {m.get('last_name','')}".strip()
            print(f"{m.get('student_id',''):<12} {name:<26} {m.get('email',''):<30} "
                  f"{m.get('phone',''):<14} {m.get('major',''):<10} {m.get('year',''):<6} {str(m.get('active', True)):<6}")
    _pause()

def menu_member_delete(mgr: MemberManager):
    print("\n=== Member > Delete ===")
    sid = _input_nonempty("Student ID to delete: ")
    confirm = input(f"Confirm delete {sid}? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        _pause()
        return
    try:
        mgr.delete_member(sid)
        print("✅ Deleted.")
    except Exception as e:
        print(f"❌ Error: {e}")
    _pause()

def menu_member_edit(mgr: MemberManager):
    print("\n=== Member > Edit ===")
    sid = _input_nonempty("Student ID to edit: ")
    curr = mgr.get_member(sid)
    if not curr:
        print("Member not found.")
        _pause()
        return

    print("\nLeave blank to keep the current value.")
    def ask(field, label):
        old = curr.get(field, "")
        return input(f"{label} [{old}]: ").strip() or ""

    first = ask("first_name", "First name")
    last  = ask("last_name",  "Last name")
    email = ask("email",      "Email")
    phone = ask("phone",      "Phone")
    major = ask("major",      "Major")
    year  = ask("year",       "Year")

    active_in = input(f"Active (true/false) [{curr.get('active', True)}]: ").strip().lower()
    active = None
    if active_in in ("true", "false"):
        active = (active_in == "true")

    try:
        mgr.edit_member(
            sid,
            first_name=first,
            last_name=last,
            email=email,
            phone=phone,
            major=major,
            year=year,
            active=active,
        )
        print("✅ Updated.")
    except Exception as e:
        print(f"❌ Error: {e}")
    _pause()

# ========================= Book Menus =========================
def menu_book_add(mgr: BookManager):
    print("\n=== Book > Add ===")
    bid   = _input_nonempty("Book ID: ")
    title = _input_nonempty("Title: ")
    author = _input_nonempty("Author: ")
    category = input("Category: ").strip()
    year  = input("Year: ").strip()
    isbn  = input("ISBN: ").strip()
    copies = input("Total copies: ").strip()
    try:
        year_v = int(year) if year and year.isdigit() else None
        copies_v = int(copies) if copies and copies.isdigit() else 1
        rec = mgr.add_book(bid, title, author, category, year_v, isbn, copies_v)
        print(f"\n✅ Added book: {rec['book_id']} - {rec['title']}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    _pause()

def menu_book_view(mgr: BookManager):
    print("\n=== Book > View ===\n")
    books = mgr.list_books()
    if not books:
        print("No books yet.")
    else:
        print(f"{'BookID':<10} {'Title':<24} {'Author':<18} {'Year':<6} {'Copies':<7} {'Avail':<7}")
        print("-" * 82)
        for b in books:
            print(f"{b.get('book_id',''):<10} {b.get('title',''):<24} {b.get('author',''):<18} "
                  f"{str(b.get('year','')):<6} {b.get('total_copies',0):<7} {b.get('available_copies',0):<7}")
    _pause()

def menu_book_delete(mgr: BookManager):
    print("\n=== Book > Delete ===")
    bid = _input_nonempty("Book ID: ")
    confirm = input(f"Confirm delete {bid}? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        _pause()
        return
    try:
        mgr.delete_book(bid)
        print("✅ Deleted book.")
    except Exception as e:
        print(f"❌ Error: {e}")
    _pause()

def menu_book_edit(mgr: BookManager):
    print("\n=== Book > Edit ===")
    bid = _input_nonempty("Book ID: ")
    curr = mgr.get_book(bid)
    if not curr:
        print("Book not found.")
        _pause()
        return
    print("Leave blank to keep old value.")
    title = input(f"Title [{curr.get('title','')}]: ").strip()
    author = input(f"Author [{curr.get('author','')}]: ").strip()
    category = input(f"Category [{curr.get('category','')}]: ").strip()
    year = input(f"Year [{curr.get('year','')}]: ").strip()
    isbn = input(f"ISBN [{curr.get('isbn','')}]: ").strip()
    copies = input(f"Total Copies [{curr.get('total_copies',1)}]: ").strip()

    try:
        updates = {}
        if title: updates["title"] = title
        if author: updates["author"] = author
        if category: updates["category"] = category
        if year and year.isdigit(): updates["year"] = int(year)
        if isbn: updates["isbn"] = isbn
        if copies and copies.isdigit():
            new_total = int(copies)
            diff = new_total - int(curr.get("total_copies", 0))
            updates["total_copies"] = new_total
            updates["available_copies"] = int(curr.get("available_copies", 0)) + diff
            if updates["available_copies"] < 0:
                raise ValueError("available_copies ติดลบไม่ได้ (จำนวนคืนต่ำกว่า ยืมอยู่)")
        mgr.edit_book(bid, **updates)
        print("✅ Updated book.")
    except Exception as e:
        print(f"❌ Error: {e}")
    _pause()

# ========================= Loan Menus =========================
def menu_loan_borrow(loan_mgr: LoanManager):
    print("\n=== Loan > Borrow ===")
    sid = _input_nonempty("Student ID: ")
    bid = _input_nonempty("Book ID: ")
    days = input("Days (default 14): ").strip()
    remarks = input("Remarks (optional): ").strip()
    try:
        days_v = int(days) if days and days.isdigit() else 14
        loan = loan_mgr.borrow(sid, bid, days_v, remarks)
        print("\n✅ Borrowed:")
        print(json.dumps(loan, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\n❌ Error: {e}")
    _pause()

def menu_loan_return(loan_mgr: LoanManager):
    print("\n=== Loan > Return ===")
    lid = _input_nonempty("Loan ID: ")
    try:
        ret = loan_mgr.return_book(lid)
        print("\n✅ Returned:")
        print(json.dumps(ret, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\n❌ Error: {e}")
    _pause()

def menu_loan_view(loan_mgr: LoanManager):
    print("\n=== Loan > View ===\n")
    loans = loan_mgr.list_loans()
    if not loans:
        print("No loans yet.")
    else:
        print(f"{'LoanID':<16} {'StudentID':<10} {'BookID':<8} {'Status':<8} {'LoanDate':<19} {'DueDate':<19} {'ReturnDate':<19}")
        print("-" * 110)
        for l in loans:
            print(f"{l.get('loan_id',''):<16} {l.get('student_id',''):<10} {l.get('book_id',''):<8} {l.get('status',''):<8} "
                  f"{l.get('loan_date',''):<19} {l.get('due_date',''):<19} {str(l.get('return_date','')):<19}")
    _pause()

def menu_loan(loan_mgr: LoanManager):
    while True:
        print("\n==== Loan Menu ====")
        print("1) Borrow")
        print("2) Return")
        print("3) View")
        print("0) Back")
        ch = input("Choose: ").strip()
        if ch == "1":
            menu_loan_borrow(loan_mgr)
        elif ch == "2":
            menu_loan_return(loan_mgr)
        elif ch == "3":
            menu_loan_view(loan_mgr)
        elif ch == "0":
            break
        else:
            print("Invalid option.")

# ========================= Report Menu =========================
def menu_report(rep_mgr: ReportManager):
    print("\n=== Report (with filters) ===")
    # include sections
    inc_m = input("Include Members? (Y/n): ").strip().lower() or "y"
    inc_b = input("Include Books?   (Y/n): ").strip().lower() or "y"
    inc_l = input("Include Loans?   (Y/n): ").strip().lower() or "y"
    # filters
    only_active_m = input("Members: active only? (y/N): ").strip().lower() == "y"

    print("Loans scope: 1) all  2) active  3) overdue  4) returned")
    scope_map = {"1":"all", "2":"active", "3":"overdue", "4":"returned"}
    scope_in = input("Choose (1-4, default 1): ").strip() or "1"
    loans_scope = scope_map.get(scope_in, "all")

    lf = input("Loans from (ISO e.g. 2025-10-01T00:00:00 or blank): ").strip()
    lt = input("Loans to   (ISO e.g. 2025-10-31T23:59:59 or blank): ").strip()

    filters = {
        "include_members": inc_m != "n",
        "include_books":   inc_b != "n",
        "include_loans":   inc_l != "n",
        "active_members_only": only_active_m,
        "loans_scope": loans_scope,
        "loans_from": lf,
        "loans_to": lt,
    }

    report = rep_mgr.build(filters)
    print("\n" + report)

    save = input("Save to file? (y/N): ").strip().lower()
    if save == "y":
        name = input("Filename (default report.txt): ").strip() or "report.txt"
        with open(name, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ Saved: {name}")
    _pause()

# ========================= Main Menu =========================
def menu_member(mem_mgr: MemberManager):
    while True:
        print("\n==== Member Menu ====")
        print("1) Add")
        print("2) Delete")
        print("3) View")
        print("4) Edit")
        print("0) Back")
        ch = input("Choose: ").strip()
        if ch == "1": menu_member_add(mem_mgr)
        elif ch == "2": menu_member_delete(mem_mgr)
        elif ch == "3": menu_member_view(mem_mgr)
        elif ch == "4": menu_member_edit(mem_mgr)
        elif ch == "0": break
        else: print("Invalid option.")

def menu_book(book_mgr: BookManager):
    while True:
        print("\n==== Book Menu ====")
        print("1) Add")
        print("2) Delete")
        print("3) View")
        print("4) Edit")
        print("0) Back")
        ch = input("Choose: ").strip()
        if ch == "1": menu_book_add(book_mgr)
        elif ch == "2": menu_book_delete(book_mgr)
        elif ch == "3": menu_book_view(book_mgr)
        elif ch == "4": menu_book_edit(book_mgr)
        elif ch == "0": break
        else: print("Invalid option.")

def main():
    mem_mgr  = MemberManager()
    book_mgr = BookManager()
    loan_mgr = LoanManager(mem_mgr=mem_mgr, book_mgr=book_mgr)
    rep_mgr  = ReportManager(mem_mgr, book_mgr, loan_mgr)

    while True:
        print("\n===== Main Menu =====")
        print("1) Member")
        print("2) Book")
        print("3) Loan")
        print("4) Report")
        print("0) Exit")
        cmd = input("Choose: ").strip()
        if cmd == "1": menu_member(mem_mgr)
        elif cmd == "2": menu_book(book_mgr)
        elif cmd == "3": menu_loan(loan_mgr)
        elif cmd == "4": menu_report(rep_mgr)
        elif cmd == "0":
            print("Bye!")
            break
        else:
            print("Invalid option.")

if __name__ == "__main__":
    main()
