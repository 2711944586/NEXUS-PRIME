type EChartsHost = {
  registerPreprocessor: (preprocessor: (option: Record<string, unknown>) => void) => void;
};

type ChartNode = Record<string, unknown>;

const LEGEND_TEXT_COLOR = 'rgba(100,116,139,.95)';
const TOOLTIP_TEXT_COLOR = 'rgba(15,23,42,.94)';
let registered = false;

export function configureEchartsLayout(echarts: EChartsHost): void {
  if (registered) {
    return;
  }

  echarts.registerPreprocessor(option => {
    normalizeLegends(option);
    normalizeInteraction(option);
    normalizePieSeries(option);
    normalizeRadar(option);
  });

  registered = true;
  if (typeof window !== 'undefined') {
    (window as typeof window & { __NEXUS_ECHARTS_LAYOUT_GUARD__?: boolean }).__NEXUS_ECHARTS_LAYOUT_GUARD__ = true;
  }
}

function normalizeInteraction(option: ChartNode): void {
  const series = toNodeList(option['series']);
  if (!series.length) {
    return;
  }

  const axisChart = hasAxis(option);
  const itemChart = series.some(item => item['type'] === 'pie' || item['type'] === 'radar');
  const tooltip = isNode(option['tooltip']) ? option['tooltip'] : {};
  const toolbox = isNode(option['toolbox']) ? option['toolbox'] : {};

  option['animationDuration'] ??= 520;
  option['animationDurationUpdate'] ??= 420;
  option['animationEasing'] ??= 'cubicOut';

  option['tooltip'] = {
    trigger: axisChart ? 'axis' : itemChart ? 'item' : tooltip['trigger'] ?? 'item',
    confine: true,
    borderWidth: 0,
    padding: [9, 11],
    backgroundColor: 'rgba(255,255,255,.96)',
    textStyle: {
      color: TOOLTIP_TEXT_COLOR,
      fontSize: 12,
      fontWeight: 700,
      ...(isNode(tooltip['textStyle']) ? tooltip['textStyle'] : {})
    },
    axisPointer: axisChart
      ? {
          type: 'cross',
          snap: true,
          label: {
            show: true,
            borderWidth: 0,
            color: '#fff',
            backgroundColor: 'rgba(15,23,42,.86)'
          },
          ...(isNode(tooltip['axisPointer']) ? tooltip['axisPointer'] : {})
        }
      : tooltip['axisPointer'],
    ...tooltip
  };

  if (axisChart) {
    normalizeAxisZoom(option);
    option['toolbox'] = {
      show: true,
      top: 4,
      right: 6,
      itemSize: 13,
      itemGap: 6,
      feature: {
        dataZoom: { yAxisIndex: 'none', title: { zoom: '框选缩放', back: '还原缩放' } },
        restore: { title: '还原' },
        saveAsImage: { title: '导出图片', pixelRatio: 2 },
        ...(isNode(toolbox['feature']) ? toolbox['feature'] : {})
      },
      ...toolbox
    };
  }

  for (const item of series) {
    const emphasis = isNode(item['emphasis']) ? item['emphasis'] : {};
    const blur = isNode(item['blur']) ? item['blur'] : {};
    item['emphasis'] = {
      focus: axisChart ? 'series' : 'self',
      blurScope: axisChart ? 'coordinateSystem' : 'global',
      ...emphasis
    };
    item['blur'] = {
      itemStyle: { opacity: 0.28, ...(isNode(blur['itemStyle']) ? blur['itemStyle'] : {}) },
      lineStyle: { opacity: 0.24, ...(isNode(blur['lineStyle']) ? blur['lineStyle'] : {}) },
      areaStyle: { opacity: 0.18, ...(isNode(blur['areaStyle']) ? blur['areaStyle'] : {}) },
      ...blur
    };
    if (item['type'] === 'line') {
      item['showSymbol'] ??= false;
      item['symbolSize'] ??= 7;
    }
  }
}

function normalizeAxisZoom(option: ChartNode): void {
  const currentZoom = toNodeList(option['dataZoom']);
  const hasInside = currentZoom.some(item => item['type'] === 'inside');
  const hasSlider = currentZoom.some(item => item['type'] === 'slider');
  const nextZoom: ChartNode[] = [...currentZoom];

  if (!hasInside) {
    nextZoom.unshift({
      type: 'inside',
      zoomOnMouseWheel: 'shift',
      moveOnMouseWheel: true,
      moveOnMouseMove: true,
      throttle: 60
    });
  }
  if (!hasSlider && shouldShowSlider(option)) {
    nextZoom.push({
      type: 'slider',
      height: 16,
      bottom: 6,
      borderColor: 'rgba(148,163,184,.26)',
      fillerColor: 'rgba(15,118,110,.16)',
      handleSize: 14,
      showDetail: false,
      brushSelect: true
    });
    normalizeGridForSlider(option);
  }

  option['dataZoom'] = nextZoom;
}

function normalizeGridForSlider(option: ChartNode): void {
  const grids = toNodeList(option['grid']);
  if (!grids.length) {
    option['grid'] = { left: 36, right: 24, top: 36, bottom: 48, containLabel: true };
    return;
  }
  for (const grid of grids) {
    grid['bottom'] ??= 48;
    grid['containLabel'] ??= true;
  }
}

function shouldShowSlider(option: ChartNode): boolean {
  const series = toNodeList(option['series']);
  const maxDataLength = Math.max(
    ...series.map(item => Array.isArray(item['data']) ? item['data'].length : 0),
    ...toNodeList(option['xAxis']).map(axis => Array.isArray(axis['data']) ? axis['data'].length : 0)
  );
  return maxDataLength >= 7;
}

function normalizeLegends(option: ChartNode): void {
  for (const legend of toNodeList(option['legend'])) {
    const textStyle = isNode(legend['textStyle']) ? legend['textStyle'] : {};
    const isTop = 'top' in legend && !('bottom' in legend);

    Object.assign(legend, {
      type: 'scroll',
      left: 8,
      right: 8,
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 10,
      pageButtonItemGap: 4,
      pageIconSize: 10,
      pageTextStyle: { color: LEGEND_TEXT_COLOR, fontSize: 10 },
      textStyle: {
        color: LEGEND_TEXT_COLOR,
        fontSize: 11,
        width: 92,
        overflow: 'truncate',
        ...textStyle
      }
    });

    if (isTop) {
      legend['top'] = 0;
    } else {
      legend['bottom'] = 0;
    }
  }
}

function normalizePieSeries(option: ChartNode): void {
  for (const series of toNodeList(option['series'])) {
    if (series['type'] !== 'pie') {
      continue;
    }

    const itemStyle = isNode(series['itemStyle']) ? series['itemStyle'] : {};
    const emphasis = isNode(series['emphasis']) ? series['emphasis'] : {};
    const emphasisLabel = isNode(emphasis['label']) ? emphasis['label'] : {};

    Object.assign(series, {
      radius: ['36%', '58%'],
      center: ['50%', '40%'],
      selectedMode: series['selectedMode'] ?? 'single',
      selectedOffset: series['selectedOffset'] ?? 8,
      avoidLabelOverlap: true,
      minAngle: 4,
      minShowLabelAngle: 8,
      label: { show: false },
      labelLine: { show: false },
      itemStyle: {
        borderRadius: 9,
        borderWidth: 2,
        borderColor: 'rgba(255,255,255,.52)',
        ...itemStyle
      },
      emphasis: {
        ...emphasis,
        scaleSize: 4,
        label: {
          show: true,
          formatter: '{b}\n{d}%',
          fontSize: 11,
          fontWeight: 800,
          color: 'inherit',
          ...emphasisLabel
        }
      }
    });
  }
}

function normalizeRadar(option: ChartNode): void {
  for (const radar of toNodeList(option['radar'])) {
    const axisName = isNode(radar['axisName']) ? radar['axisName'] : {};

    Object.assign(radar, {
      center: ['50%', '46%'],
      radius: compactRadius(radar['radius']),
      axisName: {
        color: LEGEND_TEXT_COLOR,
        fontSize: 11,
        fontWeight: 700,
        width: 72,
        overflow: 'truncate',
        ...axisName
      }
    });
  }
}

function hasAxis(option: ChartNode): boolean {
  return toNodeList(option['xAxis']).length > 0 || toNodeList(option['yAxis']).length > 0;
}

function compactRadius(value: unknown): string {
  if (typeof value === 'string' && value.endsWith('%')) {
    const number = Number(value.slice(0, -1));
    if (Number.isFinite(number) && number < 52) {
      return value;
    }
  }
  return '52%';
}

function toNodeList(value: unknown): ChartNode[] {
  if (Array.isArray(value)) {
    return value.filter(isNode);
  }
  return isNode(value) ? [value] : [];
}

function isNode(value: unknown): value is ChartNode {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
