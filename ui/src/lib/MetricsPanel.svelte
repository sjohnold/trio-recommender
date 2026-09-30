<script module lang="ts">
  export interface PercentileMetric {
    p50: number | null;
    p95: number | null;
    targetPass: boolean | null;
  }
  export interface MetricsBucket {
    language: 'ru' | 'en' | 'sr';
    mode: 'A' | 'B';
    ttft: PercentileMetric;
    full: PercentileMetric;
    round: PercentileMetric;
    personalityDrift: number | null;
    personalityDrifted: boolean | null;
    worldviewCell: string | null;
    worldviewDrifted: boolean | null;
    integrityReasons: string[] | null;
    timeoutRate: number | null;
    stateFallbackRate: number | null;
    errors: string[];
  }
  export const metricText = (
    value: number | null, suffix = ''
  ): string => value === null ? 'Insufficient data' : `${value.toFixed(2)}${suffix}`;
  export const passText = (value: boolean | null): string =>
    value === null ? 'NOT EVALUATED' : value ? 'PASS' : 'FAIL';
  export const rateText = (value: number | null): string =>
    value === null ? 'Insufficient data' : `${(value * 100).toFixed(2)}%`;
</script>

<script lang="ts">
  let { bucket }: { bucket: MetricsBucket } = $props();
  const latency = $derived([
    ['TTFT', bucket.ttft],
    ['Full generation', bucket.full],
    ['Round', bucket.round]
  ] as const);
</script>

<section aria-labelledby="metrics-title">
  <header>
    <div>
      <span>LIVE METRICS · {bucket.language.toUpperCase()} × MODE {bucket.mode}</span>
      <h3 id="metrics-title">Measured, not inferred</h3>
    </div>
    <strong>Exact language/mode bucket</strong>
  </header>
  <div class="latency">
    {#each latency as [label, metric]}
      <article class:fail={metric.targetPass === false}>
        <h4>{label}</h4>
        <dl>
          <div><dt>p50</dt><dd>{metricText(metric.p50, ' ms')}</dd></div>
          <div><dt>p95</dt><dd>{metricText(metric.p95, ' ms')}</dd></div>
        </dl>
        <b>{passText(metric.targetPass)}</b>
      </article>
    {/each}
  </div>
  <div class="signals">
    <article>
      <h4>Personality drift</h4>
      <strong>{metricText(bucket.personalityDrift)}</strong>
      <span>{bucket.personalityDrifted === null
        ? 'Insufficient data'
        : bucket.personalityDrifted ? 'DRIFT' : 'STABLE'}</span>
    </article>
    <article>
      <h4>Worldview drift</h4>
      <strong>{bucket.worldviewCell ?? 'Insufficient data'}</strong>
      <span>{bucket.worldviewDrifted === null
        ? 'Insufficient data'
        : bucket.worldviewDrifted ? 'DRIFT' : 'STABLE'}</span>
    </article>
    <article class:fail={Boolean(bucket.integrityReasons?.length)}>
      <h4>Language integrity</h4>
      <strong>{bucket.integrityReasons === null
        ? 'Insufficient data'
        : bucket.integrityReasons.length ? 'FAIL' : 'PASS'}</strong>
      <span>{bucket.integrityReasons?.join(', ') || 'No recorded violations'}</span>
    </article>
    <article>
      <h4>Reliability</h4>
      <span>Timeouts {rateText(bucket.timeoutRate)}</span>
      <span>State fallback {rateText(bucket.stateFallbackRate)}</span>
    </article>
  </div>
  {#if bucket.errors.length}
    <aside role="alert">
      <h4>Runtime errors</h4>
      <ul>{#each bucket.errors as error}<li>{error}</li>{/each}</ul>
    </aside>
  {/if}
</section>

<style>
  section { display: grid; gap: 14px; }
  header { display: flex; justify-content: space-between; }
  header span { color: #c9a86a; font: 10px monospace; }
  h3 { margin: 5px 0; font: 22px Georgia, serif; }
  .latency, .signals { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .signals { grid-template-columns: repeat(4, 1fr); }
  article, aside { border: 1px solid #504b42; background: #191714; padding: 11px; }
  article.fail { border-color: #c36f58; }
  h4 { margin: 0 0 8px; font-size: 12px; }
  dl div { display: flex; justify-content: space-between; } dl { margin: 0; }
  dt, dd, article span { color: #aaa398; font-size: 11px; }
  article > span { display: block; margin-top: 5px; }
  b { display: block; margin-top: 8px; font-size: 10px; }
  aside { color: #e99b83; }
</style>
