import { http, HttpResponse } from 'msw';
import { faker } from '@faker-js/faker';

const mockUser = {
  id: faker.string.uuid(),
  email: 'admin@example.com',
  first_name: 'Admin',
  last_name: 'User',
  role: 'ADMIN' as const,
  company: 'Acme Inc',
  phone: '+1234567890',
  is_active: true,
  date_joined: new Date().toISOString(),
  last_login: new Date().toISOString(),
};

export const authHandlers = [
  // Login – no trailing slash
  http.post('*/api/v1/auth/login', async ({ request }) => {
    const { email, password } = (await request.json()) as any;
    if (email === 'admin@example.com' && password === 'password') {
      return HttpResponse.json({
        refresh: faker.string.uuid(),
        access: faker.string.uuid(),
        user: mockUser,
      });
    }
    return HttpResponse.json(
      { detail: 'Invalid email or password.' },
      { status: 401 }
    );
  }),

  // Refresh token
  http.post('*/api/v1/auth/token/refresh', () => {
    return HttpResponse.json({
      access: faker.string.uuid(),
    });
  }),

  // Get current user
  http.get('*/api/v1/auth/users/me', () => {
    return HttpResponse.json(mockUser);
  }),

  // Register
  http.post('*/api/v1/auth/register', async ({ request }) => {
    return HttpResponse.json({
      id: faker.string.uuid(),
      email: 'newuser@example.com',
      role: 'USER',
      message: 'Registration successful. Please verify your email.',
    });
  }),

  // Password reset
  http.post('*/api/v1/auth/reset-password', () => {
    return HttpResponse.json({ detail: 'Password reset email sent.' });
  }),

  // Password reset confirm
  http.post('*/api/v1/auth/reset-password/confirm', () => {
    return HttpResponse.json({ detail: 'Password reset successful.' });
  }),
];