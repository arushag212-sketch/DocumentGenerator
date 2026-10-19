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
import uuid
from pathlib import Path
from typing import Optional

import yaml
from server.app.core import database as db_core
from server.app.core.database import Base
from server.app.core.security import get_password_hash
from server.app.core.storage import LocalDiskStorage, get_storage
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


def seed(clean: bool = False, demo_users: Optional[bool] = None):
    is_production = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    if is_production:
        if clean:
            raise RuntimeError("Refusing destructive seed reset when ENVIRONMENT=production")
        if demo_users is True:
            raise RuntimeError("Refusing to create demo users, demo passwords or platform admin account when ENVIRONMENT=production")
        demo_users = False
    else:
        if demo_users is None:
            demo_users = True

    if clean:
        # Explicit local reset remains available for development, but is never
        # inferred by a bare startup invocation.
        import sqlalchemy as sa
        with db_core.engine.connect() as conn:
            conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
            inspector = sa.inspect(conn)
            for tbl in inspector.get_table_names():
                conn.execute(sa.text(f"DROP TABLE IF EXISTS {tbl}"))
            conn.execute(sa.text("PRAGMA foreign_keys = ON;"))
            conn.commit()
        from server.scripts.migrate import run_migrations
        run_migrations()
    elif os.environ.get("SEED_BOOTSTRAP_SCHEMA", "false").lower() in ("1", "true", "yes"):
        from server.scripts.migrate import run_migrations
        run_migrations()
    db = db_core.SessionLocal()

    project_root = Path(__file__).resolve().parents[2]
    active_storage = get_storage()
    storage_assets_dir = (
        active_storage.base_dir / "assets" if isinstance(active_storage, LocalDiskStorage) else None
    )
    storage_templates_dir = (
        active_storage.base_dir / "templates" if isinstance(active_storage, LocalDiskStorage) else None
    )
    if storage_assets_dir is not None:
        storage_assets_dir.mkdir(parents=True, exist_ok=True)
        assert storage_templates_dir is not None
        storage_templates_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting database seed (production={is_production}, demo_users={demo_users})...")

    # Platform Admin accounts are NEVER seeded automatically.
    # Platform admin accounts must only be created via: python -m server.scripts.create_admin

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
        src = project_root / rel_path
        if not src.exists():
            continue
        source_bytes = src.read_bytes()
        file_hash = hashlib.sha256(source_bytes).hexdigest()
        file_size = len(source_bytes)
        storage_key = active_storage.save(f"assets/{src.name}", source_bytes)
        if isinstance(active_storage, LocalDiskStorage):
            storage_key = str(active_storage.local_path(storage_key))

        # A club-owned upload must never be silently reclassified as a system
        # asset just because it has the same filename as a bundled asset.
        asset = db.query(Asset).filter(
            Asset.filename == src.name,
            Asset.is_system.is_(True),
            Asset.club_id.is_(None),
        ).first()
        if not asset:
            asset = Asset(
                club_id=None,  # System asset
                kind="logo" if "img" in src.name else "letterhead",
                filename=src.name,
                mime=mime,
                sha256=file_hash,
                size=file_size,
                storage_key=storage_key,
                uploaded_by=None,
                is_system=True,
            )
            db.add(asset)
            db.flush()
        else:
            asset.kind = "logo" if "img" in src.name else "letterhead"
            asset.mime = mime
            asset.sha256 = file_hash
            asset.size = file_size
            asset.storage_key = storage_key
            asset.is_system = True
            db.flush()
        asset_records[key_alias] = asset
    print(f"-> Seeded {len(asset_records)} system assets")

    # 3. System Letterheads
    svnit_crest_id = asset_records.get("svnit_crest").id if asset_records.get("svnit_crest") else None
    acm_logo_id = asset_records.get("acm_logo").id if asset_records.get("acm_logo") else None

    # SVNIT Bilingual Letterhead
    lh_svnit = db.query(Letterhead).filter(
        Letterhead.name == "SVNIT Bilingual Letterhead", Letterhead.club_id.is_(None)
    ).first()
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
    lh_acm = db.query(Letterhead).filter(
        Letterhead.name == "ACM Standard Letterhead", Letterhead.club_id.is_(None)
    ).first()
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
        src_dir = project_root / "templates" / slug
        schema_path = src_dir / "schema.yaml"
        docx_path = src_dir / "template.docx"

        if not schema_path.exists() or not docx_path.exists():
            continue

        with open(schema_path, "r", encoding="utf-8") as f:
            schema_yaml_str = f.read()

        template_key = active_storage.save(f"templates/{slug}_v1.docx", docx_path.read_bytes())
        dest_docx = (
            str(active_storage.local_path(template_key))
            if isinstance(active_storage, LocalDiskStorage)
            else template_key
        )

        tmpl = db.query(Template).filter(
            Template.slug == slug,
            Template.is_system.is_(True),
            Template.club_id.is_(None),
        ).first()
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
                docx_storage_key=dest_docx,
                created_by=None,
                change_note="Initial system import from templates/",
            )
            db.add(ver)
            db.flush()
            tmpl.current_version_id = ver.id
            db.flush()
    print(f"-> Seeded {len(system_template_slugs)} system templates and versions")

    # Production startup may install/update immutable system resources, but it
    # must never create the demo club, demo people, sample credentials, or
    # dummy clubs.  Existing production data is intentionally left untouched.
    if is_production:
        db.commit()
        db.close()
        print("Production seed completed: system resources only; demo data skipped.")
        return

    # 5. Demo Club "ACM"
    with open(project_root / "config/club_config.yaml", "r", encoding="utf-8") as f:
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

    # 5.1 Seed Demo Users and Memberships (Development only)
    if demo_users:
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
                position="Student Head/Chairperson",
                status="active",
            )
            db.add(m_owner)
            db.flush()
        else:
            m_owner.position = "Student Head/Chairperson"
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
                position="Student Secretary",
                status="active",
            )
            db.add(m_sec)
            db.flush()
        else:
            m_sec.position = "Student Secretary"
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
                position="Treasurer",
                status="active",
            )
            db.add(m_tres)
            db.flush()
        else:
            m_tres.position = "Treasurer"
            db.flush()
        print("-> Seeded demo users and active memberships for ACM")
    else:
        print("-> Skipped demo users creation (production mode / demo_users=False)")

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
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="student_head", designation_label="Student Head", academic_year=club.academic_year_default))

    # Student Secretary
    if cfg_data.get("student_secretary"):
        ss = cfg_data["student_secretary"]
        p = get_or_create_person(ss.get("name"), ss.get("admission_no"), ss.get("branch"))
        people_map["student_secretary"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "student_secretary").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="student_secretary", designation_label="Student Secretary", academic_year=club.academic_year_default))

    # Chairperson
    if cfg_data.get("chairperson"):
        cp = cfg_data["chairperson"]
        p = get_or_create_person(cp.get("name"), cp.get("admission_no"), cp.get("branch"))
        people_map["chairperson"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "chairperson").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="chairperson", designation_label="Chairperson , ACM", academic_year=club.academic_year_default))

    # Faculty Chairman
    if cfg_data.get("faculty_chairman"):
        fc = cfg_data["faculty_chairman"]
        p = get_or_create_person(fc.get("name"), dept=fc.get("department"))
        people_map["faculty_chairman"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "faculty_chairman").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="faculty_chairman", designation_label="Chairman, ACM Student Chapter SVNIT", academic_year=club.academic_year_default))

    # Faculty Co-Chairman
    if cfg_data.get("faculty_co_chairman"):
        fcc = cfg_data["faculty_co_chairman"]
        p = get_or_create_person(fcc.get("name"), dept=fcc.get("department"))
        people_map["faculty_co_chairman"] = p
        r = db.query(RoleHeld).filter(RoleHeld.club_id == club.id, RoleHeld.person_id == p.id, RoleHeld.role_key == "faculty_co_chairman").first()
        if not r:
            db.add(RoleHeld(club_id=club.id, person_id=p.id, role_key="faculty_co_chairman", designation_label="Co-Chairman, ACM Student Chapter SVNIT", academic_year=club.academic_year_default))

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

    # 8. Seed Numbering Series from template schemas and config
    ay = club.academic_year_default
    from docgen.schema import load_all_schemas
    schemas = load_all_schemas()
    for s in schemas.values():
        if s.numbering and s.numbering.format:
            s_key = s.numbering.series or s.id
            ns = db.query(NumberingSeries).filter(
                NumberingSeries.club_id == club.id,
                NumberingSeries.key == s_key,
                NumberingSeries.academic_year == ay,
            ).first()
            if not ns:
                ns = NumberingSeries(
                    club_id=club.id,
                    key=s_key,
                    format=s.numbering.format,
                    academic_year=ay,
                    last_seq=0,
                )
                db.add(ns)
                db.flush()

    num_cfg = cfg_data.get("numbering", {})
    for n_key, n_val in num_cfg.items():
        ns = db.query(NumberingSeries).filter(
            NumberingSeries.club_id == club.id,
            NumberingSeries.key == n_key,
            NumberingSeries.academic_year == ay,
        ).first()
        if not ns:
            fmt = f"ACM/{{academic_year}}/{n_key}/{{seq:03d}}"
            ns = NumberingSeries(
                club_id=club.id,
                key=n_key,
                format=fmt,
                academic_year=ay,
                last_seq=n_val.get("last_used", 0),
            )
            db.add(ns)
            db.flush()
    print(f"-> Seeded numbering series for ACM")

    # 9. Seed Additional Dummy Clubs (Demo Robotics Club, Demo Cultural Club)
    additional_clubs = [
        ("Demo Robotics Club", "ROBO", "robotics", "ROBO", "robotics.lead@svnit.ac.in", "Demo Robotics Lead"),
        ("Demo Cultural Club", "CULT", "cultural", "CULT", "cultural.lead@svnit.ac.in", "Demo Cultural Lead"),
    ]
    for c_name, c_short, c_slug, c_code, c_lead_email, c_lead_name in additional_clubs:
        extra_club = db.query(Club).filter(Club.slug == c_slug).first()
        if not extra_club:
            extra_club = Club(
                name=c_name,
                short_name=c_short,
                slug=c_slug,
                chapter_code=c_code,
                head_of_account=c_code,
                academic_year_default="2026-27",
                settings={"department": "Student Welfare", "approval_chain": []},
            )
            db.add(extra_club)
            db.flush()

        # Venues
        for v_name in ("Seminar Hall", "Main Auditorium"):
            v_check = db.query(Venue).filter(Venue.club_id == extra_club.id, Venue.name == v_name).first()
            if not v_check:
                db.add(Venue(club_id=extra_club.id, name=v_name, short_name=v_name))
                db.flush()

        # Numbering
        for s_key in ("ROOM", "EVT", "MOM"):
            ns_check = db.query(NumberingSeries).filter(
                NumberingSeries.club_id == extra_club.id,
                NumberingSeries.key == s_key,
                NumberingSeries.academic_year == "2026-27",
            ).first()
            if not ns_check:
                db.add(NumberingSeries(
                    club_id=extra_club.id,
                    key=s_key,
                    format=f"{c_short}/{{academic_year}}/{s_key}/{{seq:03d}}",
                    academic_year="2026-27",
                    last_seq=0,
                ))
                db.flush()

        if demo_users:
            lead_u = db.query(User).filter(User.email == c_lead_email).first()
            if not lead_u:
                lead_u = User(
                    email=c_lead_email,
                    password_hash=get_password_hash("LeadPass123!"),
                    name=c_lead_name,
                    is_platform_admin=False,
                )
                db.add(lead_u)
                db.flush()
            m_lead = db.query(Membership).filter(Membership.club_id == extra_club.id, Membership.user_id == lead_u.id).first()
            if not m_lead:
                db.add(Membership(
                    club_id=extra_club.id,
                    user_id=lead_u.id,
                    role="owner",
                    position="Student Head/Chairperson",
                    status="active",
                ))
                db.flush()
    print("-> Seeded additional dummy clubs (Robotics, Cultural)")

    db.commit()
    db.close()
    print("Database seeding completed successfully!")
    if not is_production and demo_users:
        print("\n" + "=" * 72)
        print("DEMO CREDENTIALS (DUMMY DATA - DEVELOPMENT ONLY):")
        print("  Club Owner: demo.owner@svnit.ac.in  /  DemoOwnerPass123!   (Role: owner)")
        print("  Secretary:  secretary@svnit.ac.in   /  SecretaryPass123!   (Role: editor)")
        print("  Treasurer:  treasurer@svnit.ac.in   /  TreasurerPass123!   (Role: treasurer)")
        print("  Robo Lead:  robotics.lead@svnit.ac.in / LeadPass123!      (Role: owner)")
        print("  Cult Lead:  cultural.lead@svnit.ac.in / LeadPass123!      (Role: owner)")
        print("  (Platform Admin accounts created only via: python -m server.scripts.create_admin)")
        print("=" * 72 + "\n")
    else:
        print("Production mode: Zero demo users, zero demo passwords, zero platform admin accounts.")


if __name__ == "__main__":
    import sys
    # Bare `python -m server.scripts.seed` is an idempotent seed.  Never infer
    # a destructive reset from the absence of CLI arguments (docker startup
    # invokes the module without arguments).
    is_clean = "--clean" in sys.argv or "--reset" in sys.argv
    is_prod = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    has_demo_flag = "--demo-users" in sys.argv
    no_demo_flag = "--no-demo-users" in sys.argv
    if is_prod and has_demo_flag:
        sys.exit("Error: Refusing to create demo users, demo passwords or platform admin account when ENVIRONMENT=production")
    if has_demo_flag and no_demo_flag:
        sys.exit("Error: --demo-users and --no-demo-users cannot be used together")
    requested_demo_users = False if is_prod or no_demo_flag else True
    seed(clean=is_clean, demo_users=requested_demo_users)
