export interface User {
  id: string | number;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
  is_active: boolean;
}

export interface Club {
  id: string | number;
  code?: string;
  short_name?: string;
  name: string;
  department?: string;
  academic_year?: string;
  academic_year_default?: string;
  event_counter?: number;
  room_counter?: number;
  mom_counter?: number;
}

export type RoleName = 'owner' | 'admin' | 'lead' | 'co_lead' | 'treasurer' | 'faculty_advisor' | 'editor' | 'viewer';

export interface ClubMember {
  id: string | number;
  user_id: string | number;
  club_id: string | number;
  role: RoleName;
  title: string | null;
  created_at: string;
  user?: {
    id: string | number;
    email: string;
    full_name: string;
  };
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
}

export interface TemplateField {
  key: string;
  type: string;
  required: boolean;
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
  location?: string;
  capacity?: number;
  addressee?: string;
  tech_assistant?: string;
  faculty_in_charge?: string;
  created_at: string;
}

export interface NumberingSeries {
  id: string;
  club_id: string;
  series_key: string;
  format: string;
  academic_year: string;
  current_counter: number;
  description?: string;
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
  member_count: number;
  admin_name?: string | null;
  membership_role?: string | null;
  join_request_status?: string | null;
}

export interface JoinRequest {
  id: string;
  club_id: string;
  club_name: string;
  user_id: string;
  user_name: string;
  user_email: string;
  position: string;
  status: 'pending' | 'approved' | 'rejected';
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
}

export interface HomeGenerateResponse {
  batch_id: string;
  event_id: string;
  event_title: string;
  documents_count: number;
  zip_url: string;
  documents: HomeGeneratedDoc[];
}

