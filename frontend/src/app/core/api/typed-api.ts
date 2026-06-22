import type { components, operations, paths } from './generated/schema';
import type { DataRecord, PageResult } from '../models';

export type ApiPaths = paths;
export type ApiComponents = components;
export type ApiOperations = operations;
export type ApiPath = keyof paths;

export type ApiJsonContent<Response> = Response extends {
  content: { 'application/json': infer Body };
} ? Body : never;

export type ApiSuccessEnvelope<Operation> = Operation extends { responses: infer Responses }
  ? Responses extends { 200: infer Response }
    ? ApiJsonContent<Response>
    : Responses extends { 201: infer Response }
      ? ApiJsonContent<Response>
      : never
  : never;

export type ApiSuccessData<Operation> = ApiSuccessEnvelope<Operation> extends { data: infer Data }
  ? Data
  : never;

export type ApiResourcePage<Resource extends keyof components['schemas']> = {
  items: components['schemas'][Resource][];
  pagination: components['schemas']['PageMeta'];
};

export type ApiResourceRecord<Resource extends keyof components['schemas']> = components['schemas'][Resource] & DataRecord;
export type TypedApiResourcePage<Resource extends keyof components['schemas']> = PageResult<ApiResourceRecord<Resource>>;

export type InventoryProduct = ApiResourceRecord<'Product'>;
export type InventoryProductPage = TypedApiResourcePage<'Product'>;
export type SalesOrder = ApiResourceRecord<'Order'>;
export type SalesOrderPage = TypedApiResourcePage<'Order'>;
export type PurchaseOrder = ApiResourceRecord<'PurchaseOrder'>;
export type PurchaseOrderPage = TypedApiResourcePage<'PurchaseOrder'>;
export type FinanceReceivable = ApiResourceRecord<'Receivable'>;
export type FinanceReceivablePage = TypedApiResourcePage<'Receivable'>;
export type FinancePaymentRecord = ApiResourceRecord<'PaymentRecord'>;
export type FinancePaymentRecordPage = TypedApiResourcePage<'PaymentRecord'>;
export type FinanceCustomerCredit = ApiResourceRecord<'CustomerCredit'>;
export type FinanceCustomerCreditPage = TypedApiResourcePage<'CustomerCredit'>;
export type FinanceAccountStatement = ApiResourceRecord<'AccountStatement'>;
export type FinanceAccountStatementPage = TypedApiResourcePage<'AccountStatement'>;
