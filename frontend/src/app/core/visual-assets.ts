export interface VisualAsset {
  src: string;
  alt: string;
  label: string;
  caption: string;
}

export const OPERATIONS_VISUALS = {
  plantFloor: '/images/plant-floor.jpg',
  plantFloorDetail: '/images/plant-floor-detail.jpg',
  plantFloorWide: '/images/plant-floor-wide.jpg',
  warehouseAisles: '/images/warehouse-aisles.jpg',
  warehouseDetail: '/images/warehouse-detail.jpg',
  warehouseWide: '/images/warehouse-wide.jpg',
  industrialManufacturing: '/images/industrial-manufacturing.jpg',
  manufacturingDetail: '/images/manufacturing-detail.jpg',
  manufacturingWide: '/images/manufacturing-wide.jpg',
  operationsTeam: '/images/operations-team-wide.jpg',
  financeDashboard: '/images/finance-dashboard-wide.jpg',
  analyticsOffice: '/images/analytics-office-wide.jpg',
  planningDesk: '/images/planning-desk-wide.jpg',
  controlDashboard: '/images/control-dashboard-wide.jpg',
  mobileWorkflow: '/images/mobile-workflow-wide.jpg',
  receivingDock: '/images/receiving-dock-wide.jpg',
  scannerWorker: '/images/scanner-worker-wide.jpg',
  forkliftDock: '/images/forklift-dock-wide.jpg',
  warehouseTeam: '/images/warehouse-team-wide.jpg',
  factoryEngineers: '/images/factory-engineers-wide.jpg',
  analyticsMeeting: '/images/analytics-meeting-wide.jpg',
  customerSupport: '/images/customer-support-wide.jpg',
  archiveRecords: '/images/archive-records-wide.jpg',
  qualityInspection: '/images/quality-inspection-wide.jpg',
  maintenanceTechnician: '/images/maintenance-technician-wide.jpg',
  contractsDesk: '/images/contracts-desk-wide.jpg',
  integrationMonitor: '/images/integration-monitor-wide.jpg',
  dataQuality: '/images/data-quality-wide.jpg',
  serviceWorkorders: '/images/service-workorders-wide.jpg',
  budgetPlanning: '/images/budget-planning-wide.jpg',
  mobileScanner: '/images/mobile-scanner-wide.jpg',
  automatedProductionLine: '/images/automated-production-line-wide.jpg',
  warehouseOperatorAisle: '/images/warehouse-operator-aisle-wide.jpg',
  factoryQualityControl: '/images/factory-quality-control-wide.jpg',
  technicianRepair: '/images/technician-repair-wide.jpg',
  controlPanel: '/images/control-panel-wide.jpg',
  factorySafetyHelmet: '/images/factory-safety-helmet-wide.jpg'
} as const;

export const COMMAND_CENTER_PHOTOS: VisualAsset[] = [
  {
    src: OPERATIONS_VISUALS.plantFloorWide,
    alt: '制造车间与生产线现场',
    label: '工厂现场',
    caption: '订单、工单与收货节奏'
  },
  {
    src: OPERATIONS_VISUALS.warehouseWide,
    alt: '仓库货架与拣货通道',
    label: '仓配现场',
    caption: '库存水位、库位和履约流向'
  },
  {
    src: OPERATIONS_VISUALS.operationsTeam,
    alt: '工业制造设备与协同场景',
    label: '协同现场',
    caption: '采购、质量和经营分析'
  },
  {
    src: OPERATIONS_VISUALS.financeDashboard,
    alt: '财务分析与经营数据工作台',
    label: '财务现场',
    caption: '应收、信用与现金节奏'
  },
  {
    src: OPERATIONS_VISUALS.controlDashboard,
    alt: '运营监控和数据看板工作区',
    label: '监控现场',
    caption: '接口、规则和异常处理'
  },
  {
    src: OPERATIONS_VISUALS.mobileWorkflow,
    alt: '移动端扫码和现场协作设备',
    label: '移动现场',
    caption: '扫码盘点、收货和巡检'
  },
  {
    src: OPERATIONS_VISUALS.receivingDock,
    alt: '仓库月台与收发货现场',
    label: '收货月台',
    caption: '采购到货、验收和入库'
  },
  {
    src: OPERATIONS_VISUALS.scannerWorker,
    alt: '仓库人员使用手持终端扫码',
    label: '扫码现场',
    caption: '盘点、收货和移动任务'
  },
  {
    src: OPERATIONS_VISUALS.forkliftDock,
    alt: '叉车与仓库装卸区域',
    label: '履约月台',
    caption: '分拨、装车和客户发货'
  },
  {
    src: OPERATIONS_VISUALS.warehouseTeam,
    alt: '仓库货架与现场拣货协作',
    label: '仓库现场',
    caption: '库位、拣货和库存复核'
  },
  {
    src: OPERATIONS_VISUALS.factoryEngineers,
    alt: '工厂工程师使用平板协作',
    label: '工程现场',
    caption: '质量、产能和维护计划'
  },
  {
    src: OPERATIONS_VISUALS.analyticsMeeting,
    alt: '办公室团队围绕数据屏幕讨论经营表现',
    label: '经营复盘',
    caption: '报表、规则和数据质量治理'
  },
  {
    src: OPERATIONS_VISUALS.customerSupport,
    alt: '客服团队处理客户沟通和服务请求',
    label: '客户协同',
    caption: '客户、服务和回访动作'
  },
  {
    src: OPERATIONS_VISUALS.archiveRecords,
    alt: '档案室人员查阅纸质记录',
    label: '资料归档',
    caption: '文件、审计和知识留存'
  },
  {
    src: OPERATIONS_VISUALS.qualityInspection,
    alt: '质检人员复核工业部件',
    label: '质量现场',
    caption: '来料检验、放行和异常闭环'
  },
  {
    src: OPERATIONS_VISUALS.maintenanceTechnician,
    alt: '维护人员检查工业设备',
    label: '维护现场',
    caption: '备件、保养和工单节奏'
  },
  {
    src: OPERATIONS_VISUALS.contractsDesk,
    alt: '合同与财务文件工作台',
    label: '合同现场',
    caption: '回款窗口、合同和账龄复核'
  },
  {
    src: OPERATIONS_VISUALS.integrationMonitor,
    alt: '数据监控屏幕和接口运行图表',
    label: '接口现场',
    caption: '同步、失败重试和 SLA 追踪'
  },
  {
    src: OPERATIONS_VISUALS.dataQuality,
    alt: '数据分析仪表板与质量复核工作区',
    label: '数据治理',
    caption: '主数据、异常和体检规则'
  },
  {
    src: OPERATIONS_VISUALS.serviceWorkorders,
    alt: '服务团队协作处理客户工单',
    label: '服务现场',
    caption: '客户工单、回访和交付复盘'
  },
  {
    src: OPERATIONS_VISUALS.budgetPlanning,
    alt: '预算成本规划和财务分析工作台',
    label: '成本现场',
    caption: '预算缺口、成本和现金计划'
  },
  {
    src: OPERATIONS_VISUALS.mobileScanner,
    alt: '现场人员使用移动终端处理扫码任务',
    label: '终端现场',
    caption: '扫码、盘点和移动执行'
  },
  {
    src: OPERATIONS_VISUALS.manufacturingWide,
    alt: '制造工厂产线和设备全景',
    label: '产线现场',
    caption: '产能、工单和设备节拍'
  },
  {
    src: OPERATIONS_VISUALS.plantFloor,
    alt: '工厂生产线真实现场',
    label: '车间现场',
    caption: '制造执行和现场异常'
  },
  {
    src: OPERATIONS_VISUALS.warehouseAisles,
    alt: '仓储货架通道真实现场',
    label: '仓储通道',
    caption: '库位、批次和补货路径'
  },
  {
    src: OPERATIONS_VISUALS.plantFloorDetail,
    alt: '制造车间工位细节真实现场',
    label: '车间细节',
    caption: '工位、设备和现场节拍'
  },
  {
    src: OPERATIONS_VISUALS.warehouseDetail,
    alt: '仓库库位和货架细节真实现场',
    label: '库位细节',
    caption: '库位、物料和批次复核'
  },
  {
    src: OPERATIONS_VISUALS.manufacturingDetail,
    alt: '制造设备和产线细节真实现场',
    label: '制造细节',
    caption: '设备、工艺和质量复核'
  },
  {
    src: OPERATIONS_VISUALS.automatedProductionLine,
    alt: '自动化制造产线与工业设备',
    label: '自动化产线',
    caption: '产线节拍、设备状态和工单执行'
  },
  {
    src: OPERATIONS_VISUALS.warehouseOperatorAisle,
    alt: '仓库作业人员在货架通道处理库存',
    label: '仓储作业',
    caption: '拣货、扫码和库位复核'
  },
  {
    src: OPERATIONS_VISUALS.factoryQualityControl,
    alt: '工厂质量控制和部件检查现场',
    label: '质量复核',
    caption: '来料检验、放行和异常判定'
  },
  {
    src: OPERATIONS_VISUALS.technicianRepair,
    alt: '维修技术员检查工业设备',
    label: '维修执行',
    caption: '设备维修、备件消耗和停机窗口'
  },
  {
    src: OPERATIONS_VISUALS.controlPanel,
    alt: '工业控制面板与监控仪表',
    label: '控制面板',
    caption: '设备信号、接口状态和现场监控'
  },
  {
    src: OPERATIONS_VISUALS.factorySafetyHelmet,
    alt: '佩戴安全帽的工厂现场协作人员',
    label: '现场协作',
    caption: '班组协同、责任交接和安全巡检'
  }
];
