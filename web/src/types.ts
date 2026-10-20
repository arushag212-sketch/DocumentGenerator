export interface User {
  id: string | number;
  email: string;
  name: string;
  is_platform_admin: boolean;
  created_at?: string;
  memberships?: { club_id: string; club_name: string; club_short?: string | null; role: string; position?: string | null; status: string }[];
  /** How the account can sign in (shown on the profile page) */
  has_password?: boolean;
  uses_google?: boolean;
}

export interface Club {
  id: string | number;
  code?: string;
  short_name?: string;
  name: string;
  slug?: string;
  chapter_code?: string;
  head_of_account?: string;
  department?: string;
  academic_year?: string;
  academic_year_default?: string;
  event_counter?: number;
  room_counter?: number;
  mom_counter?: number;
  my_role?: string | null;
  settings?: Record<string, any>;
}

export type RoleName = 'owner' | 'admin' | 'lead' | 'co_lead' | 'treasurer' | 'faculty_advisor' | 'editor' | 'viewer';

export interface ClubMember {
  id: string | number;
  user_id: string | number;
  email: string;
  name: string;
  role: RoleName;
  position?: string | null;
  status: string;
  joined_at: string;
}

export interface Person {
  id: string | number;
  club_id: string | number;
  name: string;
  roll_number: string | null;
  branch: string | null;
  department?: string | null;
  designation: string | null;
  mobile: string | null;
  role: string | null;
  roles?: RoleHeld[];
  is_active: boolean;
}

export interface AuditLog {
  id: string | number;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  club_id: string | number | null;
  changes_json: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface ClubPermissions {
  is_platform_admin: boolean;
  role: RoleName | null;
  can_edit_members: boolean;
  can_edit_settings: boolean;
  can_create_documents: boolean;
  can_finalize_documents: boolean;
  can_view_sensitive: boolean;
  position?: string | null;
}

export interface TemplateField {
  key: string;
  type: string;
  required: boolean;
  importance?: 'essential' | 'optional';
  sensitive?: boolean;
  label?: string;
  ai_suggested?: boolean;
  defer_ok?: boolean;
  ask?: string;
  default_value?: any;
  default_source?: string;
  source_allowed?: string[];
  values?: string[];
}

export interface TemplateDetail {
  id: string;
  name: string;
  description: string;
  stage: string;
  fields: TemplateField[];
  defaults: Record<string, any>;
  numbering_series?: string;
  confirm_numbering?: boolean;
}

export interface DocumentVersionInfo {
  id: string;
  version_no: number;
  docx_available: boolean;
  pdf_available: boolean;
  created_at: string;
  created_by?: string;
  change_summary?: string | null;
}

export interface TableColumn {
  key: string;
  label: string;
  type?: string;
}

export interface EditableField {
  key: string;
  label: string;
  type: string;
  required: boolean;
  value: any;
  columns?: TableColumn[];
  importance?: string;
  ask?: string;
}

export interface DocumentActivity {
  id: string;
  action: 'submitted' | 'approved' | 'changes_requested' | 'comment' | 'revised' | 'emailed';
  version_no: number;
  user_name: string;
  comment?: string | null;
  verification_code?: string | null;
  created_at: string;
}

export interface ClubAnalytics {
  documents_total: number;
  documents_this_month: number;
  events_total: number;
  members: number;
  club_templates: number;
  approvals: number;
  awaiting_review: number;
  ai_requests: number;
  hours_saved: number;
  by_month: { month: string; documents: number }[];
  by_template: { name: string; count: number }[];
  by_status: Record<string, number>;
}

export interface VerificationResult {
  valid: boolean;
  document_title: string;
  ref_no?: string | null;
  club_name: string;
  version_no: number;
  approved_by: string;
  approved_at: string;
  sha256?: string | null;
  file_matches?: boolean | null;
}

export interface GeneratedDocument {
  id: string;
  club_id: string;
  template_id: string;
  title: string;
  ref_no: string | null;
  status: string;
  created_at: string;
  current_version_no: number;
  page_count: number;
  docx_url: string;
  pdf_url: string;
  page_images: string[];
  versions: DocumentVersionInfo[];
  record_snapshot: Record<string, any>;
  editable_fields?: EditableField[];
  activity?: DocumentActivity[];
  can_edit?: boolean;
  can_review?: boolean;
  template_name?: string | null;
}

export interface ExtractResult {
  extracted_data: Record<string, any>;
  provenance: Record<string, { source: string; confirmed: boolean }>;
  missing_fields: Array<{
    key: string;
    ask: string;
    documents?: string[];
    required: boolean;
  }>;
}

export interface TemplateGalleryItem {
  id: string;
  slug: string;
  name: string;
  description?: string;
  category?: string;
  stage?: string;
  is_system: boolean;
  status: string;
  forked_from_template_id?: string;
  numbering_series?: string;
  thumbnail_url?: string;
  can_fork: boolean;
  can_edit: boolean;
}

export interface RoleHeld {
  id: string;
  person_id: string;
  role_key: string;
  designation_label: string;
  academic_year: string;
  created_at: string;
}

export interface Invite {
  id: string;
  club_id: string;
  code: string;
  role: string;
  created_by?: string;
  max_uses: number;
  use_count: number;
  revoked: boolean;
  expires_at?: string;
  accepted_at?: string;
  invite_link: string;
  created_at: string;
}

export interface Venue {
  id: string;
  club_id: string;
  name: string;
  short_name?: string;
  location?: string;
  capacity?: number;
  addressee?: string;
  addressee_default?: string;
  tech_assistant?: string;
  tech_assistant_person_id?: string;
  tech_assistant_name?: string;
  faculty_in_charge?: string;
  faculty_incharge_person_id?: string;
  faculty_incharge_name?: string;
  created_at: string;
}

export interface NumberingSeries {
  id: string;
  club_id: string;
  key?: string;
  series_key: string;
  format: string;
  academic_year: string;
  last_seq?: number;
  current_counter: number;
  description?: string;
  /** Names of templates that number their documents with this series */
  used_by?: string[];
}

export interface Letterhead {
  id: string;
  club_id: string;
  name: string;
  left_logo_asset_id?: string;
  right_logo_asset_id?: string;
  institute_logo_asset_id?: string;
  title_text?: string;
  subtitle_text?: string;
  is_default: boolean;
  created_at: string;
}

export interface Asset {
  id: string;
  club_id: string;
  kind: string;
  filename: string;
  mime: string;
  size?: number;
  created_at: string;
}

export interface ClubSearchResult {
  id: string;
  name: string;
  short_name?: string;
  slug: string;
  chapter_code?: string;
  members_count: number;
  membership_status?: string | null;
  membership_position?: string | null;
  admin_name?: string | null;
  membership_role?: string | null;
  join_request_status?: string | null;
  /** The club has uploaded a logo (served from /clubs/{id}/public-logo) */
  has_logo?: boolean;
}

export interface JoinRequest {
  id: string;
  club_id: string;
  club_name: string;
  user_id: string;
  user_name: string;
  user_email: string;
  position: string;
  requested_role: 'editor' | 'viewer';
  message?: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  admin_name?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface HomeUnderstoodData {
  event_name?: string | null;
  dates?: string | null;
  date_start?: string | null;
  date_end?: string | null;
  time_start?: string | null;
  time_end?: string | null;
  venue?: string | null;
  participants?: number | null;
  description?: string | null;
  objectives?: string | null;
  raw?: Record<string, any>;
}

export interface HomeRecommendedDoc {
  template_id: string;
  name: string;
  slug: string;
  reason: string;
  recommended: boolean;
  suggested_ref_no: string;
}

export interface HomeMissingQuestion {
  key: string;
  question: string;
  label: string;
  type: string;
  required: boolean;
  importance?: 'essential' | 'optional';
  defer_ok: boolean;
  needed_by: string[];
  values?: string[] | null;
  current_value?: any;
}

export interface HomeUnderstandResponse {
  understood: HomeUnderstoodData;
  recommended_documents: HomeRecommendedDoc[];
  missing_questions: HomeMissingQuestion[];
}

export interface HomeGeneratedDoc {
  id: string;
  template_slug: string;
  title: string;
  ref_no: string;
  pdf_url: string;
  docx_url: string;
  preview_url: string;
  version_no: number;
  page_count?: number;
  page_images?: string[];
  missing_fields?: string[];
  editable_fields?: EditableField[];
  record_snapshot?: Record<string, any>;
}

export interface HomeGenerateResponse {
  batch_id: string;
  event_id: string;
  event_title: string;
  documents_count: number;
  zip_url: string;
  documents: HomeGeneratedDoc[];
  assumptions?: string[];
  notice?: string | null;
  extracted_facts?: Record<string, any>;
  missing_fields_summary?: Record<string, string[]>;
}

export interface HomeCreateResponse extends HomeGenerateResponse {
  assumptions: string[];
  notice?: string | null;
}

