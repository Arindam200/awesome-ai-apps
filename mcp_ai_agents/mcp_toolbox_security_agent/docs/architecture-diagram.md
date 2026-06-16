# Technical architecture — MCP Toolbox as the security control plane

```mermaid
flowchart LR
  %% ===================== UNTRUSTED =====================
  subgraph UNTRUSTED["⚠️ UNTRUSTED ZONE · outside the trust boundary"]
    direction TB
    U(["👤 User / Browser"])
    AGENT["🖥️ Web UI · Google ADK<br/>🧠 Kimi-K2.6 agent (LLM)<br/>sees only typed tool signatures<br/>no identity · no SQL · no credentials"]
    U --> AGENT
  end

  %% ===================== IDENTITY =====================
  KC["🔑 Keycloak (OIDC)<br/>issues signed JWT<br/>prod → Google Sign-In"]

  %% ===================== CONTROL PLANE (HERO) =====================
  subgraph TBZONE["🛡️ TRUST BOUNDARY"]
    direction TB
    TBX{{"⚙️ MCP TOOLBOX<br/>Security Control Plane"}}
    CTRL["🔐 Enforced controls<br/>#1 custom tools · no execute_sql<br/>#2 authenticated params · bind username from OIDC claim<br/>#3 authRequired · admin audience gate<br/>#4 bound params · store_region<br/>#5 parameterized SQL · $1..$n<br/>#9 OpenTelemetry on every call<br/>#10 allowed-hosts / network policy"]
    TBX --- CTRL
  end

  %% ===================== DATA =====================
  subgraph DATA["🗄️ DATA · system of record"]
    direction TB
    PG[("🐘 PostgreSQL<br/>users · products · carts · orders<br/>role: toolbox_app · least-privilege (#6)")]
    MG[("🍃 MongoDB Atlas Local<br/>$vectorSearch · Gemini embeddings<br/>role: toolbox_ro · read-only (#6)")]
  end

  %% ===================== FLOWS =====================
  KC -.->|"JWT (keycloak_token)"| AGENT
  AGENT ==>|"tool call + JWT header<br/>(no username · not in the schema)"| TBX
  KC -.->|"JWKS / OIDC discovery<br/>validate sig · issuer · audience"| TBX
  TBX ==>|"parameterized SQL<br/>WHERE username = $1 · bound from token"| PG
  TBX ==>|"vector search query"| MG

  %% ===================== PRODUCTION HARDENING =====================
  IAM["🔒 Production (GKE)<br/>#7 Cloud SQL via Workload Identity · no DB password<br/>#8 secrets via Secret Manager"]
  IAM -.->|"swaps in for the Postgres source"| TBX

  %% ===================== STYLES =====================
  classDef toolbox fill:#0e231c,stroke:#34d399,stroke-width:4px,color:#eafff5
  classDef controls fill:#10231c,stroke:#34d399,stroke-width:1px,color:#bdf3d2
  classDef untrusted fill:#1a1216,stroke:#e08a92,color:#f4d6da
  classDef data fill:#0f1c2b,stroke:#5b9dff,color:#dbeafe
  classDef idp fill:#1c1830,stroke:#a78bfa,color:#e9e2ff
  classDef prod fill:#241c10,stroke:#fbbf24,color:#ffeec2

  class TBX toolbox
  class CTRL controls
  class U,AGENT untrusted
  class PG,MG data
  class KC idp
  class IAM prod

  style TBZONE fill:#0a1713,stroke:#34d399,stroke-width:3px,color:#eafff5
  style UNTRUSTED fill:#140d10,stroke:#e08a92,stroke-dasharray:5 5,color:#f4d6da
  style DATA fill:#0a1320,stroke:#5b9dff,color:#dbeafe
```

## Legend

- **Green (bold)** — MCP Toolbox, the only component that touches data. The agent never holds a DB credential or runs raw SQL.
- **Red dashed** — the untrusted zone: the LLM and its tool arguments. Anything here is treated as hostile.
- **Solid thick arrows** — data-plane calls that Toolbox makes as a least-privilege role.
- **Dotted arrows** — identity/token flow (JWT issuance + OIDC validation).
- **#1–#10** — the ten security mechanisms (full map in [SECURITY.md](SECURITY.md)).

> Renders on GitHub, in [mermaid.live](https://mermaid.live), and VS Code's Mermaid preview.
