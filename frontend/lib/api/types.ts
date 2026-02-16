// lib/api/types.ts
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
  last_login?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  device_fingerprint?: string;
}

// Add other types as needed