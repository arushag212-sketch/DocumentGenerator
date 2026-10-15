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

export type RoleName = 'lead' | 'co_lead' | 'treasurer' | 'faculty_advisor' | 'editor' | 'viewer';

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
  designation: string | null;
  mobile: string | null;
  role: string | null;
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
