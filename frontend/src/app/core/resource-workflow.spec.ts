import { describe, expect, it } from 'vitest';

import { RESOURCE_WORKFLOW_CONFIGS, resourceConfigForUrl } from './resource-workflow';

describe('resource workflow configuration', () => {
  it('matches the current route to the most specific resource workbench', () => {
    expect(resourceConfigForUrl('/app/finance/credits?tab=limits')?.key).toBe('credits');
    expect(resourceConfigForUrl('/app/inventory/replenishment/17')?.key).toBe('replenishment');
    expect(resourceConfigForUrl('/app/content/articles#drafts')?.key).toBe('content');
    expect(resourceConfigForUrl('/auth/login')).toBeNull();
  });

  it('keeps route prefixes unique and app-scoped', () => {
    const keys = new Set<string>();
    const prefixes = new Set<string>();

    for (const config of RESOURCE_WORKFLOW_CONFIGS) {
      expect(keys.has(config.key)).toBe(false);
      keys.add(config.key);

      expect(config.routePrefixes.length).toBeGreaterThan(0);
      for (const prefix of config.routePrefixes) {
        expect(prefix.startsWith('/app/')).toBe(true);
        expect(prefixes.has(prefix)).toBe(false);
        prefixes.add(prefix);
      }
    }
  });

  it('defines enough metadata for inspect, edit and workflow surfaces', () => {
    for (const config of RESOURCE_WORKFLOW_CONFIGS) {
      expect(config.title).toBeTruthy();
      expect(config.searchPlaceholder).toBeTruthy();
      expect(config.columns.length).toBeGreaterThan(0);
      expect(config.workflowSteps.length).toBeGreaterThanOrEqual(3);

      const canMutateInline = config.createFields.length > 0 || config.editFields.length > 0 || config.actions.length > 0;
      expect(canMutateInline || Boolean(config.readonlyReason)).toBe(true);
    }
  });

  it('uses the paginated credits endpoint for the credit workbench list', () => {
    expect(resourceConfigForUrl('/app/finance/credits')?.resource).toBe('credits');
  });
});
