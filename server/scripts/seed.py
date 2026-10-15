"""Database seeding script for ClubDocs.

Seeds:
1. System Assets (SVNIT logos and headers)
2. System Letterheads (SVNIT bilingual, ACM)
3. Six System Templates (from templates/ directory into storage/templates and DB)
4. Demo Club 'ACM' with people, roles, venues, and numbering from config/club_config.yaml
"""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path

import yaml
from server.app.core.database import SessionLocal, engine, Base
from server.app.core.security import get_password_hash
from server.app.models import (
    Asset,
    Club,
    Letterhead,
    Membership,
    NumberingSeries,
    Person,
    RoleHeld,
    Template,
    TemplateVersion,
    User,
    Venue,
)


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    storage_assets_dir = Path("storage/assets")
    storage_templates_dir = Path("storage/templates")
    storage_assets_dir.mkdir(parents=True, exist_ok=True)
    storage_templates_dir.mkdir(parents=True, exist_ok=True)

    print("Starting database seed...")

    # 1. Platform Admin User
    admin = db.query(User).filter(User.email == "admin@svnit.ac.in").first()
    if not admin:
        admin = User(
            email="admin@svnit.ac.in",
            password_hash="!UNUSABLE_PASSWORD_INITIAL_SEED!",
            name="SVNIT Platform Admin",
            is_platform_admin=True,
        )
        db.add(admin)
        db.flush()
        print("-> Seeded platform admin user")

    # 2. System Assets (SVNIT logos)
    source_assets = [
        ("assets/clean_svnit_approval_header.png", "image/png", "svnit_header"),
        ("assets/permission_page1_img1.png", "image/png", "svnit_crest"),
        ("assets/permission_page1_img2.png", "image/png", "acm_logo"),
        ("assets/svnit_bilingual_header.png", "image/png", "svnit_bilingual_header"),
        ("assets/clean_permission_header.png", "image/png", "clean_permission_header"),
    ]

    asset_records = {}
    for rel_path, mime, key_alias in source_assets:
        src = Path(rel_path)
        if not src.exists():
            continue
        dest = storage_assets_dir / src.name
        shutil.copy2(src, dest)
        file_hash = compute_sha256(dest)
        file_size = dest.stat().st_size

        asset = db.query(Asset).filter(Asset.filename == src.name).first()
        if not asset:
            asset = Asset(
                club_id=None,  # System asset
                kind="logo" if "img" in src.name else "letterhead",
                filename=src.name,
                mime=mime,
                sha256=file_hash,
                size=file_size,
                storage_key=str(dest),
                uploaded_by=admin.id,
                is_system=True,
            )
            db.add(asset)
            db.flush()
        asset_records[key_alias] = asset
    print(f"-> Seeded {len(asset_records)} system assets")

    # 3. System Letterheads
    svnit_crest_id = asset_records.get("svnit_crest").id if asset_records.get("svnit_crest") else None
    acm_logo_id = asset_records.get("acm_logo").id if asset_records.get("acm_logo") else None

    # SVNIT Bilingual Letterhead
    lh_svnit = db.query(Letterhead).filter(Letterhead.name == "SVNIT Bilingual Letterhead").first()
    if not lh_svnit:
        lh_svnit = Letterhead(
            club_id=None,
            name="SVNIT Bilingual Letterhead",
            left_logo_asset_id=svnit_crest_id,
            right_logo_asset_id=None,
            institute_logo_asset_id=svnit_crest_id,
            title_text="SARDAR VALLABHBHAI NATIONAL INSTITUTE OF TECHNOLOGY, SURAT",
            subtitle_text="सरदार वल्लभभाई राष्ट्रीय प्रौद्योगिकी संस्थान, सूरत",
            colors={"primary": "#000000"},
            fonts={"primary": "Times New Roman"},
            layout={"type": "bilingual_center"},
        )
        db.add(lh_svnit)
        db.flush()

    # ACM Letterhead
    lh_acm = db.query(Letterhead).filter(Letterhead.name == "ACM Standard Letterhead").first()
    if not lh_acm:
        lh_acm = Letterhead(
            club_id=None,
            name="ACM Standard Letterhead",
            left_logo_asset_id=svnit_crest_id,
            right_logo_asset_id=acm_logo_id,
            institute_logo_asset_id=svnit_crest_id,
            title_text="ASSOCIATION FOR COMPUTING MACHINERY",
            subtitle_text="Sardar Vallabhbhai National Institute of Technology, Surat",
            colors={"primary": "#1E5B94"},
            fonts={"primary": "Times New Roman"},
            layout={"type": "dual_logo_single_line"},
        )
        db.add(lh_acm)
        db.flush()
    print("-> Seeded system letterheads")

    # 4. Six System Templates
    system_template_slugs = [
        ("permission_letter", "Permission Letter", "Permission letter for booking rooms/venues", "pre_event"),
        ("approval_note", "Approval Note", "Event financial sanction and approval note", "pre_event"),
        ("prize_money_receipt", "Prize Money Receipt", "Individual winner prize money acknowledgement", "post_event"),
        ("bill_summary", "Bill Summary", "Summary statement of bills and prize money", "post_event"),
        ("bill_certificate", "Bill Certificate", "Formal expenditure certification (Form BC-R)", "post_event"),
        ("mom", "Minutes of Meeting", "Minutes of meeting record", "meeting"),
    ]

    for slug, name, desc, stage in system_template_slugs:
        src_dir = Path("templates") / slug
        schema_path = src_dir / "schema.yaml"
        docx_path = src_dir / "template.docx"

        if not schema_path.exists() or not docx_path.exists():
            continue

        with open(schema_path, "r", encoding="utf-8") as f:
            schema_yaml_str = f.read()

        dest_docx = storage_templates_dir / f"{slug}_v1.docx"
        shutil.copy2(docx_path, dest_docx)

        tmpl = db.query(Template).filter(Template.slug == slug).first()
        if not tmpl:
            tmpl = Template(
                club_id=None,
                slug=slug,
                name=name,
                description=desc,
                category="Official Event Documents",
                stage=stage,
                is_system=True,
                status="published",
            )
            db.add(tmpl)
            db.flush()

        ver = db.query(TemplateVersion).filter(
            TemplateVersion.template_id == tmpl.id,
            TemplateVersion.version_no == 1
        ).first()
        if not ver:
            ver = TemplateVersion(
                template_id=tmpl.id,
                version_no=1,
                schema_yaml=schema_yaml_str,
                docx_storage_key=str(dest_docx),
                created_by=admin.id,
                change_note="Initial system import from templates/",
            )
            db.add(ver)
            db.flush()
            tmpl.current_version_id = ver.id
            db.flush()
    print(f"-> Seeded {len(system_template_slugs)} system templates and versions")

    # 5. Demo Club "ACM"
    with open("config/club_config.yaml", "r", encoding="utf-8") as f:
        cfg_data = yaml.safe_load(f)

    club = db.query(Club).filter(Club.slug == "acm").first()
    if not club:
        club = Club(
            name=cfg_data.get("club_name", "ACM Student Chapter, SVNIT"),
            short_name=cfg_data.get("club_short", "ACM"),
            slug="acm",
            chapter_code=cfg_data.get("chapter_code", "6/52"),
            head_of_account=cfg_data.get("head_of_account", "6/52"),
            academic_year_default=cfg_data.get("academic_year", "2026-27"),
            default_letterhead_id=lh_acm.id if lh_acm else None,
            settings={
                "institute_name": cfg_data.get("institute_name"),
                "institute_short": cfg_data.get("institute_short"),
                "affiliating_institute_text": cfg_data.get("affiliating_institute_text"),
                "defaults": cfg_data.get("defaults", {}),
                "approval_chain": cfg_data.get("approval_chain", []),
            },
        )
        db.add(club)
        db.flush()
    print(f"-> Seeded demo club: {club.name} ({club.slug})")

    # 5.1 Seed Demo Users and Memberships
    demo_owner = db.query(User).filter(User.email == "demo.owner@svnit.ac.in").first()
    if not demo_owner:
        demo_owner = User(
            email="demo.owner@svnit.ac.in",
            password_hash=get_password_hash("DemoOwnerPass123!"),
            name="Demo Club Head",
            is_platform_admin=False,
        )
        db.add(demo_owner)
        db.flush()
    else:
        demo_owner.password_hash = get_password_hash("DemoOwnerPass123!")
        demo_owner.name = "Demo Club Head"
        demo_owner.failed_login_attempts = 0
        demo_owner.locked_until = None
        db.flush()

    m_owner = db.query(Membership).filter(Membership.club_id == club.id, Membership.user_id == demo_owner.id).first()
    if not m_owner:
        m_owner = Membership(
            club_id=club.id,
            user_id=demo_owner.id,
            role="owner",
            status="active",
        )
        db.add(m_owner)
        db.flush()

    demo_lead = db.query(User).filter(User.email == "demo.lead@example.com").first()
    if not demo_lead:
        demo_lead = User(
            email="demo.lead@example.com",
            password_hash=get_password_hash("DemoSecurePass123!"),
            name="Demo Student Head",
            is_platform_admin=True,
        )
        db.add(demo_lead)
        db.flush()
    else:
        demo_lead.password_hash = get_password_hash("DemoSecurePass123!")
        demo_lead.is_platform_admin = True
        demo_lead.failed_login_attempts = 0
        demo_lead.locked_until = None
        db.flush()

    m_lead = db.query(Membership).filter(Membership.club_id == club.id, Membership.user_id == demo_lead.id).first()
    if not m_lead:
        m_lead = Membership(
            club_id=club.id,
            user_id=demo_lead.id,
            role="owner",
            status="active",
        )
        db.add(m_lead)
        db.flush()

    # Additional sample members so members count is realistic
    sec_user = db.query(User).filter(User.email == "secretary@svnit.ac.in").first()
    if not sec_user:
        sec_user = User(
            email="secretary@svnit.ac.in",
            password_hash=get_password_hash("SecretaryPass123!"),
            name="Demo Student Secretary",
            is_platform_admin=False,
        )
        db.add(sec_user)
        db.flush()
    m_sec = db.query(Membership).filter(Membership.club_id == club.id, Membership.user_id == sec_user.id).first()
    if not m_sec:
        m_sec = Membership(
            club_id=club.id,
            user_id=sec_user.id,
            role="editor",
            status="active",
        )
        db.add(m_sec)
        db.flush()

    tres_user = db.query(User).filter(User.email == "treasurer@svnit.ac.in").first()
    if not tres_user:
        tres_user = User(
            email="treasurer@svnit.ac.in",
            password_hash=get_password_hash("TreasurerPass123!"),
            name="Demo Student Treasurer",
            is_platform_admin=False,
        )
        db.add(tres_user)
        db.flush()
    m_tres = db.query(Membership).filter(Membership.club_id == club.id, Membership.user_id == tres_user.id).first()
    if not m_tres:
        m_tres = Membership(
            club_id=club.id,
            user_id=tres_user.id,
            role="treasurer",
            status="active",
        )
        db.add(m_tres)
        db.flush()
    print("-> Seeded demo users and active memberships for ACM")

    # 6. Seed People & Roles for ACM
    people_map: dict[str, Person] = {}

    def get_or_create_person(p_name, roll="", branch="", dept=""):
        if not p_name:
            return None
        person = db.query(Person).filter(Person.club_id == club.id, Person.full_name == p_name).first()
        if not person:
            person = Person(
                club_id=club.id,
                full_name=p_name,
                roll_no=roll,
                branch=branch,
                department=dept,
                mobile="",  # blank placeholder
                email="",
            )
            db.add(person)
            db.flush()
        return person

    # Student Head
    if cfg_data.get("student_head"):
        sh = cfg_data["student_head"]
        p = get_or_create_person(sh.get("name"), sh.get("admission_no"), sh.get("branch"))
        people_map["student_head"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "student_head").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="student_head", designation_label="Student Head", academic_year="2026-27"))

    # Student Secretary
    if cfg_data.get("student_secretary"):
        ss = cfg_data["student_secretary"]
        p = get_or_create_person(ss.get("name"), ss.get("admission_no"), ss.get("branch"))
        people_map["student_secretary"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "student_secretary").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="student_secretary", designation_label="Student Secretary", academic_year="2026-27"))

    # Chairperson
    if cfg_data.get("chairperson"):
        cp = cfg_data["chairperson"]
        p = get_or_create_person(cp.get("name"), cp.get("admission_no"), cp.get("branch"))
        people_map["chairperson"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "chairperson").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="chairperson", designation_label="Chairperson , ACM", academic_year="2026-27"))

    # Faculty Chairman
    if cfg_data.get("faculty_chairman"):
        fc = cfg_data["faculty_chairman"]
        p = get_or_create_person(fc.get("name"), dept=fc.get("department"))
        people_map["faculty_chairman"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "faculty_chairman").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="faculty_chairman", designation_label="Chairman, ACM Student Chapter SVNIT", academic_year="2026-27"))

    # Faculty Co-Chairman
    if cfg_data.get("faculty_co_chairman"):
        fcc = cfg_data["faculty_co_chairman"]
        p = get_or_create_person(fcc.get("name"), dept=fcc.get("department"))
        people_map["faculty_co_chairman"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "faculty_co_chairman").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="faculty_co_chairman", designation_label="Co-Chairman, ACM Student Chapter SVNIT", academic_year="2026-27"))

    # 7. Seed Venues
    venues_cfg = cfg_data.get("venues", {})
    for v_key, v_info in venues_cfg.items():
        tech_ast_p = None
        if v_info.get("tech_assistant"):
            ta = v_info["tech_assistant"]
            tech_ast_p = get_or_create_person(ta.get("name"), branch=ta.get("branch", ""))
        fac_inc_p = None
        if v_info.get("faculty_in_charge"):
            fi = v_info["faculty_in_charge"]
            fac_inc_p = get_or_create_person(fi.get("name"), branch=fi.get("branch", ""))

        v_obj = db.query(Venue).filter(Venue.club_id == club.id, Venue.name == v_key).first()
        if not v_obj:
            v_obj = Venue(
                club_id=club.id,
                name=v_key,
                short_name=v_info.get("short_name"),
                addressee_default=v_info.get("default_addressee"),
                tech_assistant_person_id=tech_ast_p.id if tech_ast_p else None,
                faculty_incharge_person_id=fac_inc_p.id if fac_inc_p else None,
            )
            db.add(v_obj)
            db.flush()
    print(f"-> Seeded venues for ACM")

    # 8. Seed Numbering Series
    num_cfg = cfg_data.get("numbering", {})
    for n_key, n_val in num_cfg.items():
        ns = db.query(NumberingSeries).filter(
            NumberingSeries.club_id == club.id,
            NumberingSeries.key == n_key,
            NumberingSeries.academic_year == "2026-27"
        ).first()
        if not ns:
            if n_key == "ROOM":
                fmt = "ACM/2026-27/ROOM/{seq:03d}"
            elif n_key == "MOM":
                fmt = "ACM/2026-27/MOM/{seq:03d}"
            elif n_key in ("approval_note", "event_approval"):
                fmt = "ACM/2026-27/{event_code}/{seq:03d}"
            else:
                fmt = f"ACM/2026-27/{n_key}/{{seq:03d}}"

            ns = NumberingSeries(
                club_id=club.id,
                key=n_key,
                format=fmt,
                academic_year="2026-27",
                last_seq=n_val.get("last_used", 0),
            )
            db.add(ns)
            db.flush()
    
    # Also explicitly ensure event_approval series exists using {academic_year}/{event_code}
    evt_ns = db.query(NumberingSeries).filter(
        NumberingSeries.club_id == club.id,
        NumberingSeries.key == "approval_note",
        NumberingSeries.academic_year == "2026-27"
    ).first()
    if not evt_ns:
        db.add(NumberingSeries(
            club_id=club.id,
            key="approval_note",
            format="ACM/2026-27/{event_code}/{seq:03d}",
            academic_year="2026-27",
            last_seq=0
        ))
        db.flush()
    print(f"-> Seeded numbering series for ACM")

    db.commit()
    db.close()
    print("Database seeding completed successfully!")
    print("\n" + "=" * 72)
    print("DEMO CREDENTIALS (DUMMY DATA):")
    print("  Club Owner: demo.owner@svnit.ac.in  /  DemoOwnerPass123!   (Role: owner)")
    print("  Club Lead:  demo.lead@example.com   /  DemoSecurePass123!  (Role: owner, Admin)")
    print("  Secretary:  secretary@svnit.ac.in   /  SecretaryPass123!   (Role: editor)")
    print("  Treasurer:  treasurer@svnit.ac.in   /  TreasurerPass123!   (Role: treasurer)")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    seed()
