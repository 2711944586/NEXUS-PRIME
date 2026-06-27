import type { AppEnvironment } from './environment.model';

export const environment: AppEnvironment = {
  production: false,
  apiBaseUrl: 'http://127.0.0.1:5001/api/v1',
  demoAccounts: {
    admin: {
      email: 'admin@nexus.com',
      password: 'admin123',
      username: 'admin',
      full_name: '庄颂'
    },
    member: {
      email: 'user00001@nexus.com',
      password: 'password123',
      username: 'user001',
      full_name: '运营成员'
    }
  }
};
