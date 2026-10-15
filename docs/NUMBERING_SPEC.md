# Reference Numbering & Reservation Specification

## 1. Overview
In institutional document workflows, reference numbers (e.g. `ACM/2026-27/SIH/001` or `ACM/ROOM/2026-27/001`) serve as legal identifiers for approvals, venue bookings, and minutes of meetings. To prevent collisions under concurrent use and prevent unauthorized or arbitrary numbering, reference numbers are allocated atomically via a two-phase reservation protocol.

---

## 2. Reservation Lifecycle

```
[ Unallocated ]
       │
       ▼  POST /api/v1/clubs/{id}/numbering/{series_key}/reserve
 [ Reserved ]  (expires in 30 minutes, bound to club_id, user_id, series_key)
       │
       ├──────────────────────────────────────────────┐
       ▼ (Generation within 30 min)                   ▼ (Unused / Expired >30 min)
   [ Used ]                                      [ Released / Expired ]
(Linked to Document,                          (Intentional Audit Gap;
 unique (club_id, ref_no))                     NEVER recycled or reused)
```

1. **Atomic Allocation**:
   - `POST /api/v1/clubs/{club_id}/numbering/{series_key}/reserve`
   - Atomically locks the series counter via PostgreSQL `SELECT ... FOR UPDATE` (or SQLite serialized lock).
   - Increments the sequence number `last_seq += 1`.
   - Generates the official reference number formatting with the club's active academic year (e.g., from club settings `academic_year_default`), club short name, and event code or template prefix.
   - Stores a `NumberReservation` record with:
     - `reservation_id` (UUID)
     - `club_id`
     - `user_id`
     - `series_key`
     - `ref_no`
     - `status`: `"reserved"`
     - `reserved_at`: `datetime.utcnow()`
     - `expires_at`: `datetime.utcnow() + timedelta(minutes=30)`

2. **Strict Generation Validation**:
   - `POST /api/v1/clubs/{club_id}/documents/generate` requires `reservation_id` for any template with a numbering configuration.
   - Verifies:
     - Reservation exists in the club.
     - Reservation belongs to the requesting user (`user_id`).
     - Series matches the template's required series.
     - Reservation status is currently `"reserved"`.
     - Reservation is not expired (`expires_at > datetime.utcnow()`).
     - If client sent a `ref_no` string, it must strictly match `reservation.ref_no` (manual fabricated strings like `ROOM/777` are rejected with `INVALID_REF_NO`).
   - On successful document generation:
     - Reservation status transitions to `"used"`.
     - `Document` is saved with `ref_no` enforced by a database unique constraint: `UniqueConstraint("club_id", "ref_no", name="uq_document_club_ref_no")`.

3. **Gaps and Audit Policy**:
   - Reference numbers associated with expired or cancelled reservations are **NEVER** reused or rolled back.
   - Any unfinalized or expired reservation represents a permanent documented audit gap in the numbering sequence.
   - This ensures institutional integrity: once a number is printed, distributed, or previewed with an official series, another document can never claim that same identifier.

---

## 3. Database Schema

### `number_reservations` Table
| Column | Type | Description |
|---|---|---|
| `id` | VARCHAR(36) PK | UUID reservation token |
| `club_id` | VARCHAR(36) FK | References `clubs.id` |
| `user_id` | VARCHAR(36) FK | References `users.id` |
| `series_key` | VARCHAR(64) | Series category (e.g. `ROOM`, `MOM`, or event code) |
| `ref_no` | VARCHAR(128) | Formatted reference string |
| `status` | VARCHAR(32) | `reserved`, `used`, `released`, `expired` |
| `reserved_at` | TIMESTAMP | Creation timestamp |
| `expires_at` | TIMESTAMP | Expiration timestamp (30 minutes after reservation) |
| `used_at` | TIMESTAMP | Document generation timestamp |

### `documents` Table Unique Constraint
- `uq_document_club_ref_no`: `UNIQUE (club_id, ref_no)` (excluding NULLs) prevents duplicate reference numbers within any club.
