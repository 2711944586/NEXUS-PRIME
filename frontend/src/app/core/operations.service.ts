import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ApiService } from './api.service';
import { observableQuery } from './domain-query';
import {
  ErpControlTower,
  MaintenanceReliabilityPayload,
  ManufacturingCommandCenter,
  OperationsWorkflowBoard,
  ProcurementControlPayload,
  QualityInspectionPayload,
  SupplierCollaborationPayload,
} from './models';

@Injectable({ providedIn: 'root' })
export class OperationsService {
  private readonly api = inject(ApiService);

  commandCenter(): Observable<ManufacturingCommandCenter> {
    return this.api.get('overview/command-center');
  }

  commandCenterQuery() {
    return observableQuery(['domains', 'operations', 'command-center'], () => this.commandCenter());
  }

  workflowBoard(): Observable<OperationsWorkflowBoard> {
    return this.api.get('overview/workflow-board');
  }

  workflowBoardQuery() {
    return observableQuery(['domains', 'operations', 'workflow-board'], () => this.workflowBoard());
  }

  controlTower(): Observable<ErpControlTower> {
    return this.api.get('overview/control-tower');
  }

  controlTowerQuery() {
    return observableQuery(['domains', 'operations', 'control-tower'], () => this.controlTower());
  }

  procurementControl(): Observable<ProcurementControlPayload> {
    return this.api.get('operations/procurement-control');
  }

  procurementControlQuery() {
    return observableQuery(['domains', 'operations', 'procurement-control'], () => this.procurementControl());
  }

  supplierCollaboration(): Observable<SupplierCollaborationPayload> {
    return this.api.get('operations/supplier-collaboration');
  }

  supplierCollaborationQuery() {
    return observableQuery(['domains', 'operations', 'supplier-collaboration'], () => this.supplierCollaboration());
  }

  qualityInspection(): Observable<QualityInspectionPayload> {
    return this.api.get('operations/quality-inspection');
  }

  qualityInspectionQuery() {
    return observableQuery(['domains', 'operations', 'quality-inspection'], () => this.qualityInspection());
  }

  maintenance(): Observable<MaintenanceReliabilityPayload> {
    return this.api.get('operations/maintenance');
  }

  maintenanceQuery() {
    return observableQuery(['domains', 'operations', 'maintenance'], () => this.maintenance());
  }

  dispatchTask(payload: Record<string, unknown>): Observable<unknown> {
    return this.api.post('operations/dispatch-task', payload);
  }
}
