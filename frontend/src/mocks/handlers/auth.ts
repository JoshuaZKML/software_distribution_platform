import { http, HttpResponse } from 'msw';
import { faker } from '@faker-js/faker';

// Load user from localStorage on worker start (persists across page reloads)
let currentUser: any = null;
if (typeof localStorage !== 'undefined') {
  const storedUser = localStorage.getItem('msw-user');
  if (storedUser) {
    try {
      currentUser = JSON.parse(storedUser);
    } catch {
      currentUser = null;
    }
  }
}

export const authHandlers = [
  // Login – sets currentUser and persists in localStorage
  http.post('/api/v1/auth/login', async ({ request }) => {
    const { email, password } = (await request.json()) as any;
    if (email === 'admin@example.com' && password === 'password') {
      currentUser = {
        id: faker.string.uuid(),
        email: 'admin@example.com',
        first_name: 'Admin',
        last_name: 'User',
        role: 'ADMIN',
        company: 'Acme Inc',
        phone: '+1234567890',
        is_active: true,
        date_joined: new Date().toISOString(),
        last_login: new Date().toISOString(),
      };
      localStorage.setItem('msw-user', JSON.stringify(currentUser));
      return HttpResponse.json({
        refresh: faker.string.uuid(),
        access: faker.string.uuid(),
        user: currentUser,
      });
    }
    return HttpResponse.json(
      { detail: 'Invalid email or password.' },
      { status: 401 }
    );
  }),

  // Refresh token – only succeeds if a user is logged in
  http.post('/api/v1/auth/token/refresh', () => {
    if (currentUser) {
      return HttpResponse.json({
        access: faker.string.uuid(),
      });
    }
    return HttpResponse.json(
      { detail: 'No active user session.' },
      { status: 401 }
    );
  }),

  // Get current user – only returns 200 if logged in
  http.get('/api/v1/auth/users/me', () => {
    if (currentUser) {
      return HttpResponse.json(currentUser);
    }
    return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
  }),

  // Logout – clear currentUser and remove from localStorage
  http.post('/api/v1/auth/logout', () => {
    currentUser = null;
    localStorage.removeItem('msw-user');
    return HttpResponse.json({});
  }),

  // Register
  http.post('/api/v1/auth/register', async ({ request }) => {
    return HttpResponse.json({
      id: faker.string.uuid(),
      email: 'newuser@example.com',
      role: 'USER',
      message: 'Registration successful. Please verify your email.',
    });
  }),

  // Password reset
  http.post('/api/v1/auth/reset-password', () => {
    return HttpResponse.json({ detail: 'Password reset email sent.' });
  }),
  http.post('/api/v1/auth/reset-password/confirm', () => {
    return HttpResponse.json({ detail: 'Password reset successful.' });
  }),
];