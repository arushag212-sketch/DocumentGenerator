# SVNIT ClubDocs — Non-Technical Club Member User Guide

Welcome to **SVNIT ClubDocs**! This guide is written for student chapter officers, event convenors, secretaries, and treasurers who need to generate official permissions, sanction notes, and expenditure certificates without manual Word formatting or number tracking errors.

---

## 1. Joining Your Club

### Option A: Via an Invite Link (Recommended)
1. Your Club Administrator will send you an invite link (e.g., `http://localhost:8000/?invite=ACM-A7B8C9`).
2. Open the link in any web browser (Chrome, Firefox, Edge, Safari, or on your mobile phone).
3. You will see a banner confirming your club and assigned role (e.g. *Join ACM Student Chapter as Editor*).
4. Enter your full name, SVNIT email address, and choose a secure password (minimum 10 characters).
5. Click **Create Account**. You are immediately logged in and connected to your club!

### Option B: Logging in with Existing Account
1. Open the portal at [http://localhost:8000](http://localhost:8000).
2. Enter your email and password, then click **Sign In**.
3. Select your active club from the top-right **Club Switcher** dropdown.

---

## 2. Generating an Official Document Package in 3 Steps

Instead of manually drafting separate letters, permission requests, and approval notes, ClubDocs generates your entire coordinated package from a single plain-English description.

### Step 1: Describe Your Event
1. Click the **Events** tab in the top navigation bar.
2. In the text box, describe what your club is planning:
   > *"We are conducting a two-day Web Development Workshop on 14-15 October in Seminar Hall for around 120 students."*
3. Click **Analyze & Recommend Documents**.

### Step 2: Review Recommendations & Complete Information
1. **Document Checklist**: The system automatically checks the documents you need (e.g. *Permission Letter* for venue booking + *Event Approval Note* for institutional sanction). You can check or uncheck documents if needed.
2. **Missing Information Form**:
   - The portal shows a neat list of details needed across all documents.
   - Enter shared details **once** (e.g., start time: `09:00 AM`, end time: `05:00 PM`, submitted to: `Head of Department`).
   - If AI suggested a summary or objectives, review it and click **Accept**.
3. **Reference Numbers & Academic Year**:
   - Verify the suggested reference numbers (e.g. `ACM/26-27/ROOM/001`).
   - Check the box: **"Confirm reference numbers to be reserved on generate"**.
   - Confirm the inferred academic year (e.g. `2026`).

> [!NOTE]
> **Why is the Generate button disabled?**
> The generate button protects you from submitting incomplete letters. It unlocks once:
> 1. All required fields are filled.
> 2. Any AI-drafted text has been accepted.
> 3. The reference numbers confirmation checkbox is ticked.

### Step 3: Download Your Package
1. Click **Generate Selected Documents**.
2. Within 2-3 seconds, the portal:
   - Allocates official serial numbers.
   - Creates formatted DOCX files.
   - Converts them to standard SVNIT PDF documents.
   - Bundles everything into a single `.zip` file.
3. Click **Download Complete ZIP** to save the archive to your computer or phone.

---

## 3. Finding and Reviewing Documents

1. Click the **Documents** tab in the navigation bar.
2. Use the **Search bar** to quickly locate documents by reference number (`ACM/26-27/ROOM/001`) or keywords from the title.
3. Click **Review →** to open any document:
   - View metadata (creation timestamp, author, academic year).
   - Check version history (`v1`, `v2`, etc.).
   - Click **Download PDF** or **Download DOCX** at any time.

---

## 4. Updating an Event & Generating Version 2 (v2)

If your venue or event timing changes after generating:
1. Go to the **Events** tab and find your event in the list.
2. Click **Edit Event Details**.
3. Update the venue or title (e.g., change venue to *DoCSE Lab 1*).
4. Keep the checkbox **"Re-render existing documents as new version (v2)"** checked.
5. Click **Update Event**.
6. The system automatically creates `v2` of every document, keeping the original serial number intact and recording the update in the audit log.

---

## 5. Mobile Friendly Usage

SVNIT ClubDocs is designed to work seamlessly on mobile browsers:
- Navigation tabs scroll smoothly without horizontal page jumping.
- Large tap targets for buttons and checkboxes.
- Instant access on your phone during club committee meetings or when collecting faculty signatures.

---

## 6. Frequently Asked Questions (FAQ)

### What if my event has student winners or cash prizes?
In the Events tab, check the **Prize Money Receipt** document. A simple table will appear where you can enter each winner's name, roll number, and prize amount. ClubDocs will generate individual, numbered receipts for each winner in the same batch.

### What if our club needs a custom letter format?
Club administrators can go to **Template Gallery**, fork any standard template, and customize paragraph wording, logos, or signatories using the interactive editor.

### Who can view masked contact numbers?
To protect student and faculty privacy, contact phone numbers are encrypted at rest with Fernet AES-128 and displayed as `XXXXXX...`. Only authenticated Club Administrators have permission to reveal plaintext numbers for official communication.
