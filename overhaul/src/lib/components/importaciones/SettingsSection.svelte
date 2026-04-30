<script lang="ts">
  let { title, defaultOpen = true, children } = $props<{
    title: string;
    defaultOpen?: boolean;
    children: any;
  }>();

  let open = $state(defaultOpen);
</script>

<section class="settings-section">
  <button class="settings-section__head" onclick={() => (open = !open)} aria-expanded={open}>
    <span class="caret" class:open>▸</span>
    <span class="title">{title}</span>
  </button>
  {#if open}
    <div class="settings-section__body">
      {@render children()}
    </div>
  {/if}
</section>

<style>
  .settings-section {
    border: 1px solid var(--border, #22222a);
    border-radius: 4px;
    margin-bottom: 12px;
    background: var(--surface-1, #0f0f12);
  }
  .settings-section__head {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: transparent;
    border: 0;
    cursor: pointer;
    text-align: left;
    color: inherit;
  }
  .settings-section__head:hover {
    background: var(--surface-2, #16161b);
  }
  .caret {
    display: inline-block;
    transition: transform 0.15s;
    color: var(--accent, #5b8def);
  }
  .caret.open { transform: rotate(90deg); }
  .title {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 12px;
    font-weight: 600;
  }
  .settings-section__body {
    padding: 8px 16px 16px;
    border-top: 1px solid var(--border, #22222a);
  }
</style>
