"use client";

import { useId, useState } from "react";

export function useProviderFilter<T extends { provider: string }>(rows: T[]) {
  const [provider, setProvider] = useState<string>("All Providers");
  const providers = [...new Set(rows.map((r) => r.provider))].sort();
  const filtered =
    provider === "All Providers" ? rows : rows.filter((r) => r.provider === provider);
  return { provider, setProvider, providers, filtered };
}

export function ProviderSelect({
  provider,
  providers,
  onChange,
}: {
  provider: string;
  providers: string[];
  onChange: (p: string) => void;
}) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-sm text-zinc-500 dark:text-zinc-400">
        Provider
      </label>
      <select
        id={id}
        value={provider}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-blue-200 dark:border-blue-400/25 bg-white/80 dark:bg-blue-500/5 text-sm px-2.5 py-1 font-mono text-zinc-700 dark:text-zinc-200 outline-none transition-colors focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30"
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
