"""Interactive Three.js viewer for the generated STL, embedded via st.components.

The part "prints" itself in on load: a clipping plane sweeps up layer by layer
over a print bed, then the camera orbits freely.
"""

from __future__ import annotations

import base64
import json

THREE_VERSION = "0.170.0"


def viewer_html(stl_bytes: bytes, color: str = "#f28c33", size_mm: list[float] | None = None, height: int = 520) -> str:
    b64 = base64.b64encode(stl_bytes).decode()
    dims = " × ".join(f"{v:.1f}" for v in size_mm) + " mm" if size_mm else ""
    return f"""
<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;height:100%;background:#0c0e0d;overflow:hidden;font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
  #wrap{{position:relative;width:100%;height:{height}px;border-radius:14px;overflow:hidden}}
  canvas{{display:block}}
  .hud{{position:absolute;left:14px;top:12px;color:#e9ede8;font-size:13px;letter-spacing:.02em;
       background:rgba(12,14,13,.62);padding:6px 10px;border-radius:8px;border:1px solid rgba(255,255,255,.08)}}
  .hud b{{color:#b7f34a;font-weight:600}}
  .btns{{position:absolute;right:12px;top:12px;display:flex;gap:8px}}
  button{{background:rgba(12,14,13,.7);color:#e9ede8;border:1px solid rgba(255,255,255,.14);border-radius:8px;
         padding:6px 10px;font-size:12px;cursor:pointer}}
  button:hover{{border-color:#b7f34a;color:#b7f34a}}
  #layer{{position:absolute;left:14px;bottom:12px;color:#9ca49d;font-size:12px;font-variant-numeric:tabular-nums}}
</style>
<script type="importmap">
{{"imports":{{"three":"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/build/three.module.js",
"three/addons/":"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/examples/jsm/"}}}}
</script>
</head><body>
<div id="wrap">
  <div class="hud"><b>STL</b>&nbsp; {dims}</div>
  <div class="btns"><button id="replay">↻ Replay print</button><button id="spin">⟳ Auto-rotate</button></div>
  <div id="layer"></div>
</div>
<script type="module">
import * as THREE from "three";
import {{ OrbitControls }} from "three/addons/controls/OrbitControls.js";
import {{ STLLoader }} from "three/addons/loaders/STLLoader.js";

const wrap = document.getElementById("wrap");
const W = () => wrap.clientWidth, H = () => wrap.clientHeight;

const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(W(), H());
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.localClippingEnabled = true;
wrap.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0c0e0d);

const raw = Uint8Array.from(atob("{b64}"), c => c.charCodeAt(0)).buffer;
const geom = new STLLoader().parse(raw);
geom.rotateX(-Math.PI / 2);           // CAD is Z-up, three.js is Y-up
geom.computeBoundingBox();
const bb = geom.boundingBox, size = new THREE.Vector3(); bb.getSize(size);
geom.translate(-(bb.min.x + bb.max.x) / 2, -bb.min.y, -(bb.min.z + bb.max.z) / 2);
const maxDim = Math.max(size.x, size.y, size.z);

const clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
const mat = new THREE.MeshPhysicalMaterial({{
  color: {json.dumps(color)}, roughness: 0.42, metalness: 0.0, clearcoat: 0.25,
  clippingPlanes: [clip], side: THREE.DoubleSide
}});
const mesh = new THREE.Mesh(geom, mat);
mesh.castShadow = true; mesh.receiveShadow = true;
scene.add(mesh);

const edges = new THREE.LineSegments(
  new THREE.EdgesGeometry(geom, 28),
  new THREE.LineBasicMaterial({{ color: 0x1a1a1a, transparent: true, opacity: 0.35, clippingPlanes: [clip] }})
);
scene.add(edges);

// Print bed: 220 mm square with a 10 mm grid.
const bedSize = Math.max(220, Math.ceil(maxDim * 1.6 / 10) * 10);
const bed = new THREE.Mesh(new THREE.PlaneGeometry(bedSize, bedSize),
  new THREE.MeshStandardMaterial({{ color: 0x161a17, roughness: 0.9 }}));
bed.rotation.x = -Math.PI / 2; bed.receiveShadow = true; scene.add(bed);
const grid = new THREE.GridHelper(bedSize, bedSize / 10, 0x3c463d, 0x252b26);
grid.position.y = 0.05; scene.add(grid);

// Glowing layer plane that rides the clipping height while "printing".
const glow = new THREE.Mesh(new THREE.PlaneGeometry(size.x * 1.25 + 4, size.z * 1.25 + 4),
  new THREE.MeshBasicMaterial({{ color: 0xb7f34a, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false }}));
glow.rotation.x = -Math.PI / 2; scene.add(glow);

scene.add(new THREE.HemisphereLight(0xffffff, 0x2a2f2b, 0.9));
const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(maxDim * 1.2, maxDim * 2, maxDim * 0.9);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
const s = maxDim * 1.5;
Object.assign(key.shadow.camera, {{ left: -s, right: s, top: s, bottom: -s, near: 0.1, far: maxDim * 6 }});
scene.add(key);
const rim = new THREE.DirectionalLight(0xb7f34a, 0.6);
rim.position.set(-maxDim, maxDim * 0.6, -maxDim); scene.add(rim);

const camera = new THREE.PerspectiveCamera(40, W() / H(), 0.1, maxDim * 50);
camera.position.set(maxDim * 1.35, maxDim * 1.05, maxDim * 1.55);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, size.y * 0.42, 0);
controls.enableDamping = true;
controls.autoRotateSpeed = 1.6;
controls.update();

const layerEl = document.getElementById("layer");
let t0 = performance.now();
const DURATION = 2200;
document.getElementById("replay").onclick = () => {{ t0 = performance.now(); }};
document.getElementById("spin").onclick = () => {{ controls.autoRotate = !controls.autoRotate; }};

function tick(now) {{
  const k = Math.min(1, (now - t0) / DURATION);
  const eased = 1 - Math.pow(1 - k, 2);
  const h = eased * (size.y + 0.01);
  clip.constant = k < 1 ? h : size.y + 10;
  glow.position.y = h;
  glow.material.opacity = k < 1 ? 0.22 : Math.max(0, glow.material.opacity - 0.01);
  layerEl.textContent = k < 1 ? `printing layer ${{Math.round(h / 0.2)}} / ${{Math.round(size.y / 0.2)}}` : "";
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}}
requestAnimationFrame(tick);

new ResizeObserver(() => {{
  renderer.setSize(W(), H()); camera.aspect = W() / H(); camera.updateProjectionMatrix();
}}).observe(wrap);
</script>
</body></html>
"""
