export type DemoAccountRole = 'admin' | 'member';

export interface DemoAccount {
  email: string;
  password: string;
  username: string;
  full_name: string;
}

export interface AppEnvironment {
  production: boolean;
  apiBaseUrl: string;
  demoAccounts: Partial<Record<DemoAccountRole, DemoAccount>>;
}
