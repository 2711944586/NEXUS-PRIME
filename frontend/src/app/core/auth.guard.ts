import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isAuthenticated()) {
    return true;
  }
  if (!auth.hasSessionCookieHint()) {
    return router.createUrlTree(['/auth/login'], { queryParams: { redirect: state.url } });
  }
  return auth.refreshCurrentUser().pipe(
    map(user => user ? true : router.createUrlTree(['/auth/login'], { queryParams: { redirect: state.url } })),
    catchError(() => of(router.createUrlTree(['/auth/login'], { queryParams: { redirect: state.url } })))
  );
};

export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isAuthenticated()) {
    return router.createUrlTree(['/app/overview']);
  }
  return true;
};
