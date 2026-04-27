<script lang="ts">
  interface DataPoint {
    date: string;
    value: number;
    label?: string;
  }

  interface Props {
    data: DataPoint[];
    width?: number;
    height?: number;
    strokeColor?: string;
    fillColor?: string;
    yAxisLabel?: string;
  }

  let {
    data,
    width = 280,
    height = 140,
    strokeColor = 'var(--color-accent)',
    fillColor = 'rgba(74,222,128,0.12)',
    yAxisLabel = ''
  }: Props = $props();

  const PADDING = { top: 10, right: 10, bottom: 24, left: 36 };

  let innerWidth = $derived(width - PADDING.left - PADDING.right);
  let innerHeight = $derived(height - PADDING.top - PADDING.bottom);

  let maxVal = $derived(Math.max(...data.map(d => d.value), 1));
  const minVal = 0;

  function xPos(i: number): number {
    if (data.length <= 1) return PADDING.left + innerWidth / 2;
    return PADDING.left + (i / (data.length - 1)) * innerWidth;
  }

  function yPos(v: number): number {
    return PADDING.top + (1 - (v - minVal) / (maxVal - minVal || 1)) * innerHeight;
  }

  let polylinePoints = $derived(data.map((d, i) => `${xPos(i)},${yPos(d.value)}`).join(' '));
  let areaPath = $derived(
    data.length > 0
      ? `M ${xPos(0)} ${PADDING.top + innerHeight} L ${data.map((d, i) => `${xPos(i)} ${yPos(d.value)}`).join(' L ')} L ${xPos(data.length - 1)} ${PADDING.top + innerHeight} Z`
      : ''
  );

  let yTicks = $derived(
    [0, 0.25, 0.5, 0.75, 1].map(p => ({
      value: minVal + (maxVal - minVal) * p,
      y: PADDING.top + (1 - p) * innerHeight,
    }))
  );

  let xTickInterval = $derived(Math.max(1, Math.ceil(data.length / 6)));
</script>

<svg {width} {height} viewBox="0 0 {width} {height}" class="block">
  {#each yTicks as tick}
    <line
      x1={PADDING.left} y1={tick.y}
      x2={width - PADDING.right} y2={tick.y}
      stroke="var(--color-border)" stroke-width="0.5" stroke-dasharray="2,3"
    />
    <text
      x={PADDING.left - 4} y={tick.y + 3}
      text-anchor="end" font-size="8" fill="var(--color-text-muted)"
      font-family="monospace"
    >{Math.round(tick.value)}</text>
  {/each}

  {#each data as d, i}
    {#if i % xTickInterval === 0 || i === data.length - 1}
      <text
        x={xPos(i)} y={height - PADDING.bottom + 12}
        text-anchor="middle" font-size="8" fill="var(--color-text-muted)"
        font-family="monospace"
      >{d.date.slice(5)}</text>
    {/if}
  {/each}

  {#if yAxisLabel}
    <text
      x={PADDING.left - 28} y={PADDING.top + innerHeight / 2}
      transform="rotate(-90 {PADDING.left - 28} {PADDING.top + innerHeight / 2})"
      text-anchor="middle" font-size="8" fill="var(--color-text-tertiary)"
    >{yAxisLabel}</text>
  {/if}

  {#if areaPath}
    <path d={areaPath} fill={fillColor} />
  {/if}

  {#if data.length > 1}
    <polyline points={polylinePoints} fill="none" stroke={strokeColor} stroke-width="1.5" />
  {/if}

  {#each data as d, i}
    <circle
      cx={xPos(i)} cy={yPos(d.value)} r="2"
      fill={strokeColor}
    >
      <title>{d.date}: {d.value}{d.label ? ` (${d.label})` : ''}</title>
    </circle>
  {/each}
</svg>
