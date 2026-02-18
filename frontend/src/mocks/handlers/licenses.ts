import { http, HttpResponse } from 'msw';
import { faker } from '@faker-js/faker';

const generateLicense = () => ({
  id: faker.string.uuid(),
  software_name: faker.company.name() + ' Software',
  software_slug: faker.helpers.slugify(faker.company.name()).toLowerCase(),
  human_code:
    faker.string
      .alphanumeric(25)
      .toUpperCase()
      .match(/.{5}/g)
      ?.join('-') || '',
  license_type: faker.helpers.arrayElement([
    'TRIAL',
    'STANDARD',
    'PREMIUM',
    'ENTERPRISE',
    'LIFETIME',
  ]),
  status: faker.helpers.arrayElement(['ACTIVATED', 'INACTIVE', 'EXPIRED']),
  user_email: faker.internet.email(),
  max_activations: 5,
  activation_count: faker.number.int({ min: 0, max: 5 }),
  expires_at: faker.date.future().toISOString(),
  is_valid: true,
  remaining_activations: faker.number.int({ min: 0, max: 5 }),
  device_fingerprint: faker.string.alphanumeric(32),
  device_name: faker.helpers.arrayElement([
    'Windows PC',
    'MacBook Pro',
    'Linux Workstation',
  ]),
});

export const licensesHandlers = [
  http.get('*/api/v1/licenses/my-licenses/', () => {
    return HttpResponse.json({
      summary: {
        total: 10,
        active: 7,
        expiring_soon: 2,
      },
      licenses_by_software: [
        {
          software_name: 'Product A',
          software_slug: 'product-a',
          licenses: faker.helpers.multiple(generateLicense, { count: 3 }),
        },
        {
          software_name: 'Product B',
          software_slug: 'product-b',
          licenses: faker.helpers.multiple(generateLicense, { count: 2 }),
        },
      ],
    });
  }),

  http.get('*/api/v1/licenses/activation-codes/:id/', ({ params }) => {
    return HttpResponse.json(generateLicense());
  }),
];
