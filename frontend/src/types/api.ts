// src/types/api.ts

export interface Software {
  id: string;
  name: string;
  slug: string;
  app_code: string;
  category: string | null;
  category_name: string;
  short_description?: string;
  full_description?: string;
  features?: any;
  requirements?: string;
  tags?: string[];
  base_price: string;
  currency: string;
  license_type: 'PERPETUAL' | 'SUBSCRIPTION' | 'TRIAL' | 'FLOATING' | 'CONCURRENT';
  pricing_tiers: string;
  has_trial: boolean;
  trial_days?: number;
  trial_features?: any;
  is_active: boolean;
  is_featured: boolean;
  is_new: boolean;
  display_order: number;
  download_count: number;
  average_rating: number;
  review_count: number;
  supported_os: string;
  current_version: string;
  versions: SoftwareVersion[];
  images: SoftwareImage[];
  documents: SoftwareDocument[];
  released_at: string;
  created_at: string;
  updated_at: string;
}

export interface SoftwareVersion {
  id: string;
  version_number: string;
  version_code: string;
  release_name?: string;
  release_notes?: string;
  changelog?: string;
  binary_file?: string;
  binary_size?: number;
  file_size_human?: string;
  binary_checksum?: string;
  installer_file?: string | null;
  download_url?: string;
  download_count: number;
  supported_os?: any;
  min_requirements?: any;
  recommended_requirements?: any;
  is_active: boolean;
  is_beta: boolean;
  is_stable: boolean;
  is_signed: boolean;
  signature_file?: string | null;
  created_at: string;
  updated_at: string;
  released_at: string;
}

export interface SoftwareImage {
  id: string;
  image_type: 'LOGO' | 'SCREENSHOT' | 'BANNER' | 'ICON' | 'OTHER';
  image_url: string;
  thumbnail_url: string;
  alt_text?: string;
  caption?: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

export interface SoftwareDocument {
  id: string;
  document_type: 'MANUAL' | 'GUIDE' | 'API' | 'LICENSE' | 'RELEASE_NOTES' | 'OTHER';
  title: string;
  file_url: string;
  file_size: string;
  file_type: string;
  description?: string;
  language: string;
  version: string;
  download_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SoftwareRequest {
  name: string;
  slug: string;
  app_code: string;
  category?: string | null;
  short_description?: string;
  full_description?: string;
  features?: any;
  requirements?: string;
  tags?: string[];
  base_price: string;
  currency: string;
  license_type: 'PERPETUAL' | 'SUBSCRIPTION' | 'TRIAL' | 'FLOATING' | 'CONCURRENT';
  has_trial?: boolean;
  trial_days?: number;
  trial_features?: any;
  is_active?: boolean;
  is_featured?: boolean;
  is_new?: boolean;
  display_order?: number;
  released_at?: string;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: 'USER' | 'ADMIN' | 'SUPER_ADMIN';
  company?: string;
  phone?: string;
  is_active: boolean;
  date_joined: string;
  updated_at: string;
  last_login: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
  device_fingerprint?: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user?: User;
}