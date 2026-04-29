"use client";

export function ProviderSelect({
  id,
  provider,
  providers,
  onChange,
}: {
  id: string;
  provider: string;
  providers: string[];
  onChange: (p: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-sm text-zinc-500 dark:text-zinc-400">
        Provider
      </label>
      <select
        id={id}
        value={provider}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-sm px-2 py-1 font-mono text-zinc-700 dark:text-zinc-300"
      >
        <option value="All Providers">All Providers</option>
        {providers.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
    </div>
  );
}
