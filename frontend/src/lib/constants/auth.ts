// Centralized token keys – matches API response
export const ACCESS_TOKEN_KEY = process.env.NEXT_PUBLIC_JWT_STORAGE_KEY || 'access';
export const REFRESH_TOKEN_KEY = process.env.NEXT_PUBLIC_REFRESH_STORAGE_KEY || 'refresh';