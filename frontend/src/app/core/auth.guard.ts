import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';

import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isAuthenticated()) return true;
  if (!auth.hasSessionCookieHint()) {
    return router.createUrlTree(['/auth/login'], { queryParams: { redirect: state.url } });
  }
  // shareReplay in refreshCurrentUser() prevents concurrent /auth/me calls
  return auth.refreshCurrentUser().pipe(map(user =>
    user ? true : router.createUrlTree(['/auth/login'], { queryParams: { redirect: state.url } })
  ));
};

export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  // Only redirect if we have both a valid user object AND the session cookie,
  // avoiding the dead-lock where cookie exists but JWT is expired.
  if (auth.isAuthenticated()) {
    return router.createUrlTree(['/app/overview']);
  }
  return true;
};
