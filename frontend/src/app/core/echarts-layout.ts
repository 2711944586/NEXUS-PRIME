type EChartsHost = {
  registerPreprocessor: (preprocessor: (option: Record<string, unknown>) => void) => void;
  getInstanceByDom?: (dom: HTMLElement) => EChartsInstance | undefined;
};

type ChartNode = Record<string, unknown>;
type EChartsInstance = {
  getOption: () => ChartNode;
  setOption: (option: ChartNode, opts?: { notMerge?: boolean; lazyUpdate?: boolean; silent?: boolean }) => void;
  resize: () => void;
};

const LEGEND_TEXT_COLOR = 'rgba(100,116,139,.95)';
const TOOLTIP_TEXT_COLOR = 'rgba(15,23,42,.94)';
const CHART_THEMES = {
  light: {
    palette: ['#1f6f8b', '#27836f', '#9b752c', '#b91c1c', '#6d6f93', '#475569'],
    text: 'rgba(16,32,51,.92)',
    muted: 'rgba(48,63,84,.82)',
    faint: 'rgba(48,63,84,.68)',
    grid: 'rgba(34,49,68,.14)',
    axis: 'rgba(34,49,68,.2)',
    tooltipBackground: 'rgba(255,255,255,.98)',
    tooltipText: 'rgba(7,20,33,.96)',
    tooltipPointer: 'rgba(31,88,117,.9)',
    pieBorder: 'rgba(255,255,255,.76)',
    zoomFill: 'rgba(31,111,139,.16)'
  },
  dark: {
    palette: ['#76d8ff', '#68e0bd', '#d6ad55', '#fb7185', '#b497cf', '#c5d5cf'],
    text: 'rgba(248,250,252,.92)',
    muted: 'rgba(226,239,255,.76)',
    faint: 'rgba(226,239,255,.62)',
    grid: 'rgba(148,163,184,.18)',
    axis: 'rgba(148,163,184,.24)',
    tooltipBackground: 'rgba(8,13,22,.94)',
    tooltipText: 'rgba(248,250,252,.94)',
    tooltipPointer: 'rgba(96,165,250,.86)',
    pieBorder: 'rgba(8,13,22,.72)',
    zoomFill: 'rgba(118,216,255,.16)'
  }
} as const;

type ChartTheme = typeof CHART_THEMES[keyof typeof CHART_THEMES];
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
    normalizeTheme(option);
  });

  registered = true;
  if (typeof window !== 'undefined') {
    (window as typeof window & { __NEXUS_ECHARTS_LAYOUT_GUARD__?: boolean }).__NEXUS_ECHARTS_LAYOUT_GUARD__ = true;
    window.addEventListener('nexus-theme-change', () => refreshRenderedCharts(echarts), { passive: true });
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

  option['animation'] = false;
  option['animationDuration'] = 0;
  option['animationDurationUpdate'] = 0;
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

function normalizeTheme(option: ChartNode): void {
  const theme = currentChartTheme();
  option['backgroundColor'] = 'transparent';
  option['color'] = Array.isArray(option['color']) && option['color'].length ? option['color'] : [...theme.palette];

  normalizeThemeLegends(option, theme);
  normalizeThemeAxes(option, theme);
  normalizeThemeTooltip(option, theme);
  normalizeThemeToolbox(option, theme);
  normalizeThemeZoom(option, theme);
  normalizeThemeSeries(option, theme);
  normalizeThemeRadar(option, theme);
}

function normalizeThemeLegends(option: ChartNode, theme: ChartTheme): void {
  for (const legend of toNodeList(option['legend'])) {
    const textStyle = ensureNode(legend, 'textStyle');
    legend['pageTextStyle'] = { ...(isNode(legend['pageTextStyle']) ? legend['pageTextStyle'] : {}), color: theme.faint, fontSize: 10 };
    legend['pageIconColor'] = theme.muted;
    legend['pageIconInactiveColor'] = theme.axis;
    legend['inactiveColor'] = theme.faint;
    legend['textStyle'] = {
      ...textStyle,
      color: theme.muted,
      fontSize: textStyle['fontSize'] ?? 11,
      overflow: textStyle['overflow'] ?? 'truncate'
    };
  }
}

function normalizeThemeAxes(option: ChartNode, theme: ChartTheme): void {
  for (const axis of [...toNodeList(option['xAxis']), ...toNodeList(option['yAxis'])]) {
    const axisLabel = ensureNode(axis, 'axisLabel');
    const axisLine = ensureNode(axis, 'axisLine');
    const axisLineStyle = ensureNode(axisLine, 'lineStyle');
    const splitLine = ensureNode(axis, 'splitLine');
    const splitLineStyle = ensureNode(splitLine, 'lineStyle');
    const nameTextStyle = ensureNode(axis, 'nameTextStyle');

    axis['axisLabel'] = {
      ...axisLabel,
      color: theme.faint,
      fontWeight: axisLabel['fontWeight'] ?? 700,
      hideOverlap: axisLabel['hideOverlap'] ?? true
    };
    axisLine['lineStyle'] = { ...axisLineStyle, color: theme.axis };
    splitLine['lineStyle'] = { ...splitLineStyle, color: theme.grid };
    axis['nameTextStyle'] = { ...nameTextStyle, color: theme.faint, fontWeight: nameTextStyle['fontWeight'] ?? 700 };
  }
}

function normalizeThemeTooltip(option: ChartNode, theme: ChartTheme): void {
  const tooltip = ensureNode(option, 'tooltip');
  const textStyle = ensureNode(tooltip, 'textStyle');
  tooltip['backgroundColor'] = theme.tooltipBackground;
  tooltip['borderColor'] = 'transparent';
  tooltip['extraCssText'] = 'box-shadow: 0 14px 34px rgba(15,23,42,.16); border-radius: 10px;';
  tooltip['textStyle'] = { ...textStyle, color: theme.tooltipText, fontSize: textStyle['fontSize'] ?? 12, fontWeight: textStyle['fontWeight'] ?? 700 };

  if (isNode(tooltip['axisPointer'])) {
    const axisPointer = tooltip['axisPointer'];
    if (isNode(axisPointer['label'])) {
      axisPointer['label'] = {
        ...axisPointer['label'],
        color: '#ffffff',
        backgroundColor: theme.tooltipPointer
      };
    }
    if (isNode(axisPointer['lineStyle'])) {
      axisPointer['lineStyle'] = { ...axisPointer['lineStyle'], color: theme.axis };
    }
  }
}

function normalizeThemeToolbox(option: ChartNode, theme: ChartTheme): void {
  const toolbox = isNode(option['toolbox']) ? option['toolbox'] : null;
  if (!toolbox) {
    return;
  }
  toolbox['iconStyle'] = {
    ...(isNode(toolbox['iconStyle']) ? toolbox['iconStyle'] : {}),
    borderColor: theme.faint
  };
  toolbox['emphasis'] = {
    ...(isNode(toolbox['emphasis']) ? toolbox['emphasis'] : {}),
    iconStyle: {
      ...(isNode(toolbox['emphasis']) && isNode(toolbox['emphasis']['iconStyle']) ? toolbox['emphasis']['iconStyle'] : {}),
      borderColor: theme.text
    }
  };
}

function normalizeThemeZoom(option: ChartNode, theme: ChartTheme): void {
  for (const zoom of toNodeList(option['dataZoom'])) {
    zoom['borderColor'] = theme.axis;
    zoom['fillerColor'] = theme.zoomFill;
    zoom['textStyle'] = { ...(isNode(zoom['textStyle']) ? zoom['textStyle'] : {}), color: theme.faint };
    zoom['handleStyle'] = {
      ...(isNode(zoom['handleStyle']) ? zoom['handleStyle'] : {}),
      color: theme.muted,
      borderColor: theme.axis
    };
  }
}

function normalizeThemeSeries(option: ChartNode, theme: ChartTheme): void {
  const series = toNodeList(option['series']);
  for (const [index, item] of series.entries()) {
    const color = theme.palette[index % theme.palette.length];
    const itemStyle = ensureNode(item, 'itemStyle');
    const lineStyle = ensureNode(item, 'lineStyle');

    if (!('color' in itemStyle) && (item['type'] === 'bar' || item['type'] === 'pie' || item['type'] === 'treemap')) {
      itemStyle['color'] = color;
    }
    if (item['type'] === 'line' && !('color' in lineStyle)) {
      lineStyle['color'] = color;
    }
    if (item['type'] === 'pie') {
      itemStyle['borderColor'] = itemStyle['borderColor'] ?? theme.pieBorder;
    }

    const label = isNode(item['label']) ? item['label'] : null;
    if (label && !('color' in label)) {
      label['color'] = theme.text;
    }
  }
}

function normalizeThemeRadar(option: ChartNode, theme: ChartTheme): void {
  for (const radar of toNodeList(option['radar'])) {
    const axisName = ensureNode(radar, 'axisName');
    const splitLine = ensureNode(radar, 'splitLine');
    const splitLineStyle = ensureNode(splitLine, 'lineStyle');
    const axisLine = ensureNode(radar, 'axisLine');
    const axisLineStyle = ensureNode(axisLine, 'lineStyle');

    radar['axisName'] = { ...axisName, color: theme.muted, fontWeight: axisName['fontWeight'] ?? 700 };
    splitLine['lineStyle'] = { ...splitLineStyle, color: theme.grid };
    axisLine['lineStyle'] = { ...axisLineStyle, color: theme.axis };
  }
}

function currentChartTheme(): ChartTheme {
  if (typeof document !== 'undefined' && document.documentElement.classList.contains('dark-cockpit')) {
    return CHART_THEMES.dark;
  }
  return CHART_THEMES.light;
}

function refreshRenderedCharts(echarts: EChartsHost): void {
  if (typeof document === 'undefined' || typeof window === 'undefined' || !echarts.getInstanceByDom) {
    return;
  }
  window.requestAnimationFrame(() => {
    for (const element of document.querySelectorAll<HTMLElement>('[_echarts_instance_]')) {
      const instance = echarts.getInstanceByDom?.(element);
      if (!instance) {
        continue;
      }
      const option = instance.getOption();
      instance.setOption(option, { notMerge: false, lazyUpdate: true, silent: true });
      instance.resize();
    }
  });
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

function ensureNode(parent: ChartNode, key: string): ChartNode {
  const value = parent[key];
  if (isNode(value)) {
    return value;
  }
  const next: ChartNode = {};
  parent[key] = next;
  return next;
}
