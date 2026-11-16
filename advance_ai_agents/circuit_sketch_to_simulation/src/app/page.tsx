import Link from "next/link";
import { Start } from "@/components/Start";
import { listExamples } from "@/lib/examples";
import { listRuns, type Run } from "@/lib/runs";

export const dynamic = "force-dynamic";

function runStatus(r: Run) {
  if (r.status === "failed") return <span className="status bad">Failed</span>;
  if (r.status !== "done") return <span className="status run">Running</span>;
  if (r.result?.agrees) return <span className="status ok">Solver agrees</span>;
  return <span className="status maybe">Solver disagrees</span>;
}

export default async function Home() {
  const [examples, runs] = await Promise.all([listExamples(), listRuns()]);
  return (
    <>
      <section className="hero">
        <h1>From a sketch to a working circuit</h1>
        <p>
          Photograph a hand-drawn circuit, mistakes and all. Inkling 2 Small reads it, finds what is wrong and builds an interactive simulation.
          It then checks that simulation by looking at screenshots of it, and a circuit solver checks every number.
        </p>
      </section>
      <hr className="gradient-rule" />
      <div style={{ padding: "40px 0 64px" }} className="stack">
        <Start examples={examples.map(({ id, file, name, licence, author }) => ({ id, file, name, licence, author }))} />
        {runs.length > 0 && (
          <section className="stack" style={{ marginTop: 24 }}>
            <h3>Recent runs</h3>
            <div className="runs">
              {runs.slice(0, 20).map((r) => (
                <Link key={r.id} href={`/run/${r.id}`} className="run-row">
                  <img src={`/api/runs/${r.id}/files/sketch.jpg`} alt="" />
                  <div>
                    <div>{r.read?.title ?? r.sketch.source?.name ?? "Sketch"}</div>
                    <div className="faint caption">{new Date(r.createdAt).toLocaleString("en-GB")}</div>
                  </div>
                  {runStatus(r)}
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  );
}
