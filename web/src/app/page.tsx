export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Vélib Wizard</h1>
      <p className="text-zinc-500 max-w-md text-center">
        Dashboard scaffolding is in place. Map, station detail, favorites and network
        analytics views land in M2 onward.
      </p>
      <code className="text-xs text-zinc-400">M1 · skeleton</code>
    </main>
  );
}
