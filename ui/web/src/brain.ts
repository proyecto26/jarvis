/**
 * Procedural 3D brain — Three.js, generated geometry only (no model assets).
 *
 * Composition:
 *  - ~7000-particle point cloud: two hemispheres built from noise-displaced
 *    ellipsoid shells (72% cortex surface, 28% interior volume), split by a
 *    midline gap. Custom point shader does breathing/ripple/beat/jitter on
 *    the GPU — zero per-frame vertex uploads.
 *  - ~380 neural connection lines between nearby cortex points; a shader
 *    pulse travels each segment (synapse firing), speed/intensity driven by
 *    agent state.
 *  - Sparse far starfield for the dark space-like backdrop; slow camera
 *    drift; slow whole-brain rotation.
 *
 * State mapping (agent.state):
 *   idle      → slow breathing pulse, faint synapse traffic
 *   listening → ripple wave travelling front→back (toward the user)
 *   thinking  → fast synapse firing + particle jitter
 *   speaking  → rhythmic waves; each chat.delta calls beat() for a word-pulse
 * system.mode tints the palette: awake=cyan/blue, reflective=violet,
 * sleep=dim deep blue.
 *
 * Performance: all uniforms are scalar/Color objects mutated in place; the
 * render loop allocates nothing.
 */
import * as THREE from 'three';
import type { AgentState, SystemMode } from './protocol';

const PARTICLES = 7000;
const MAX_SEGMENTS = 380;
const STARS = 450;

interface StateParams {
  breath: number;
  ripple: number;
  activity: number;
  fireSpeed: number;
  fireIntensity: number;
  size: number;
}

const STATE_PARAMS: Record<AgentState, StateParams> = {
  idle: { breath: 1.0, ripple: 0.0, activity: 0.0, fireSpeed: 0.18, fireIntensity: 0.4, size: 1.0 },
  listening: { breath: 0.5, ripple: 1.0, activity: 0.08, fireSpeed: 0.35, fireIntensity: 0.55, size: 1.05 },
  thinking: { breath: 0.35, ripple: 0.0, activity: 1.0, fireSpeed: 1.8, fireIntensity: 1.5, size: 1.1 },
  speaking: { breath: 0.75, ripple: 0.15, activity: 0.22, fireSpeed: 0.8, fireIntensity: 1.0, size: 1.08 },
};

interface ModePalette {
  a: THREE.Color;
  b: THREE.Color;
  dim: number;
}

const MODE_PALETTES: Record<SystemMode, ModePalette> = {
  awake: { a: new THREE.Color('#1560d4'), b: new THREE.Color('#43e8ff'), dim: 1.0 },
  reflective: { a: new THREE.Color('#5b2bd6'), b: new THREE.Color('#d96bff'), dim: 0.9 },
  sleep: { a: new THREE.Color('#0c1f52'), b: new THREE.Color('#3a5fb0'), dim: 0.45 },
};

/** Cheap layered sine "noise" for cortex wrinkles — deterministic, no deps. */
function wrinkle(x: number, y: number, z: number): number {
  return (
    Math.sin(x * 6.1 + y * 3.3) * 0.35 +
    Math.sin(y * 7.7 + z * 4.9) * 0.3 +
    Math.sin(z * 5.3 + x * 8.1) * 0.35
  );
}

const POINTS_VERT = /* glsl */ `
uniform float uTime;
uniform float uBreath;
uniform float uRipple;
uniform float uActivity;
uniform float uBeat;
uniform float uSize;
attribute float aSeed;
attribute float aShell;
varying float vGlow;

void main() {
  vec3 p = position;
  float t = uTime;
  float scale = 1.0
    + uBreath * 0.035 * sin(t * 1.15 + aSeed * 6.2831)
    + uBeat   * 0.075 * sin(t * 9.0 + aSeed * 40.0)
    + uRipple * 0.06  * sin(p.z * 5.0 - t * 4.2 + aSeed * 1.7);
  p *= scale;
  p += uActivity * 0.028 * vec3(
    sin(t * 13.0 + aSeed * 91.0),
    sin(t * 17.0 + aSeed * 57.0),
    sin(t * 11.0 + aSeed * 73.0));

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  float twinkle = 0.6 + 0.4 * sin(t * (2.0 + 10.0 * uActivity) + aSeed * 100.0);
  vGlow = twinkle * (0.35 + 0.65 * aShell);
  gl_PointSize = uSize * (0.6 + 0.9 * aSeed) * twinkle * (17.0 / -mv.z);
  gl_Position = projectionMatrix * mv;
}
`;

const POINTS_FRAG = /* glsl */ `
uniform vec3 uColorA;
uniform vec3 uColorB;
uniform float uDim;
varying float vGlow;

void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d2 = dot(c, c);
  if (d2 > 0.25) discard;
  float alpha = smoothstep(0.25, 0.0, d2) * vGlow * uDim * 0.85;
  vec3 col = mix(uColorA, uColorB, clamp(vGlow, 0.0, 1.0));
  gl_FragColor = vec4(col, alpha);
}
`;

const LINES_VERT = /* glsl */ `
uniform float uFirePhase;
attribute float aPhase;
attribute float aT;
varying float vPulse;

void main() {
  float pulse = fract(uFirePhase + aPhase);
  float d = aT - pulse;
  vPulse = exp(-d * d * 40.0);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const LINES_FRAG = /* glsl */ `
uniform vec3 uColorB;
uniform float uFireIntensity;
uniform float uDim;
varying float vPulse;

void main() {
  float alpha = (0.05 + vPulse * 0.4 * uFireIntensity) * uDim;
  gl_FragColor = vec4(uColorB, alpha);
}
`;

export class Brain {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene: THREE.Scene;
  private readonly camera: THREE.PerspectiveCamera;
  private readonly group: THREE.Group;

  private readonly pointsUniforms: {
    uTime: { value: number };
    uBreath: { value: number };
    uRipple: { value: number };
    uActivity: { value: number };
    uBeat: { value: number };
    uSize: { value: number };
    uDim: { value: number };
    uColorA: { value: THREE.Color };
    uColorB: { value: THREE.Color };
  };
  private readonly linesUniforms: {
    uFirePhase: { value: number };
    uFireIntensity: { value: number };
    uDim: { value: number };
    uColorB: { value: THREE.Color };
  };

  // CPU-side animation state, lerped toward targets each frame.
  private readonly current: StateParams = { ...STATE_PARAMS.idle };
  private target: StateParams = STATE_PARAMS.idle;
  private readonly colorA = MODE_PALETTES.awake.a.clone();
  private readonly colorB = MODE_PALETTES.awake.b.clone();
  private paletteTarget: ModePalette = MODE_PALETTES.awake;
  private dim = MODE_PALETTES.awake.dim;
  private beatLevel = 0;
  private firePhase = 0;
  private lastMs = performance.now();

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x04050a, 1);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    this.camera.position.set(0, 0.2, 3.4);

    this.group = new THREE.Group();
    this.scene.add(this.group);

    this.pointsUniforms = {
      uTime: { value: 0 },
      uBreath: { value: 1 },
      uRipple: { value: 0 },
      uActivity: { value: 0 },
      uBeat: { value: 0 },
      uSize: { value: 1 },
      uDim: { value: 1 },
      uColorA: { value: this.colorA },
      uColorB: { value: this.colorB },
    };
    this.linesUniforms = {
      uFirePhase: { value: 0 },
      uFireIntensity: { value: 0.4 },
      uDim: { value: 1 },
      uColorB: { value: this.colorB },
    };

    const { pointsGeo, linesGeo } = buildBrainGeometry();

    const pointsMat = new THREE.ShaderMaterial({
      uniforms: this.pointsUniforms,
      vertexShader: POINTS_VERT,
      fragmentShader: POINTS_FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.group.add(new THREE.Points(pointsGeo, pointsMat));

    const linesMat = new THREE.ShaderMaterial({
      uniforms: this.linesUniforms,
      vertexShader: LINES_VERT,
      fragmentShader: LINES_FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.group.add(new THREE.LineSegments(linesGeo, linesMat));

    this.scene.add(buildStarfield());

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.renderer.setAnimationLoop(() => this.frame());
  }

  setAgentState(state: AgentState): void {
    this.target = STATE_PARAMS[state];
  }

  setSystemMode(mode: SystemMode): void {
    this.paletteTarget = MODE_PALETTES[mode];
  }

  /** One rhythmic pulse per streamed chat.delta while speaking. */
  beat(): void {
    this.beatLevel = 1;
  }

  private resize(): void {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private frame(): void {
    const now = performance.now();
    const dt = Math.min((now - this.lastMs) / 1000, 0.05);
    this.lastMs = now;
    const t = now / 1000;

    // Smooth state transitions: exponential approach toward targets.
    const k = 1 - Math.exp(-3.2 * dt);
    const cur = this.current;
    const tgt = this.target;
    cur.breath += (tgt.breath - cur.breath) * k;
    cur.ripple += (tgt.ripple - cur.ripple) * k;
    cur.activity += (tgt.activity - cur.activity) * k;
    cur.fireSpeed += (tgt.fireSpeed - cur.fireSpeed) * k;
    cur.fireIntensity += (tgt.fireIntensity - cur.fireIntensity) * k;
    cur.size += (tgt.size - cur.size) * k;
    this.dim += (this.paletteTarget.dim - this.dim) * k;
    this.colorA.lerp(this.paletteTarget.a, k);
    this.colorB.lerp(this.paletteTarget.b, k);

    // Word-beat decay (speaking) and accumulated fire phase (rate-smooth).
    this.beatLevel *= Math.exp(-4.5 * dt);
    this.firePhase += cur.fireSpeed * dt;

    const pu = this.pointsUniforms;
    pu.uTime.value = t;
    pu.uBreath.value = cur.breath;
    pu.uRipple.value = cur.ripple;
    pu.uActivity.value = cur.activity;
    pu.uBeat.value = this.beatLevel;
    pu.uSize.value = cur.size;
    pu.uDim.value = this.dim;

    const lu = this.linesUniforms;
    lu.uFirePhase.value = this.firePhase;
    lu.uFireIntensity.value = cur.fireIntensity;
    lu.uDim.value = this.dim;

    // Subtle camera drift + slow brain rotation.
    this.camera.position.x = Math.sin(t * 0.08) * 0.45;
    this.camera.position.y = 0.18 + Math.sin(t * 0.05) * 0.1;
    this.camera.position.z = 3.4 + Math.sin(t * 0.037) * 0.12;
    this.camera.lookAt(0, 0, 0);
    this.group.rotation.y = t * 0.05;

    this.renderer.render(this.scene, this.camera);
  }
}

/** Try to create the brain; returns null when WebGL is unavailable. */
export function createBrain(canvas: HTMLCanvasElement): Brain | null {
  try {
    return new Brain(canvas);
  } catch (err) {
    console.warn('[dante] WebGL unavailable, brain disabled:', err);
    return null;
  }
}

function buildBrainGeometry(): {
  pointsGeo: THREE.BufferGeometry;
  linesGeo: THREE.BufferGeometry;
} {
  const positions = new Float32Array(PARTICLES * 3);
  const seeds = new Float32Array(PARTICLES);
  const shells = new Float32Array(PARTICLES);
  // Cortex-surface points kept flat for the connection pass.
  const shellPts: number[] = [];

  for (let i = 0; i < PARTICLES; i++) {
    // Uniform direction on the unit sphere.
    const u = Math.random() * 2 - 1;
    const phi = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const dx = s * Math.cos(phi);
    const dy = u;
    const dz = s * Math.sin(phi);

    const isShell = Math.random() < 0.72;
    let r: number;
    if (isShell) {
      // Wrinkled cortex: radial noise displacement + slight scatter.
      r = 1 + 0.085 * wrinkle(dx * 2.3, dy * 2.3, dz * 2.3) + (Math.random() - 0.5) * 0.03;
    } else {
      // Interior volume, biased outward.
      r = Math.cbrt(Math.random()) * 0.9;
    }

    // Ellipsoid proportions of a brain: wider than tall, longest front-back.
    let x = dx * r * 0.98;
    let y = dy * r * 0.8;
    const z = dz * r * 1.28;

    // Longitudinal fissure: two hemispheres separated by a midline gap.
    x += x >= 0 ? 0.055 : -0.055;
    // Flatten the underside a little (brain stem side).
    if (y < -0.42) y = -0.42 + (y + 0.42) * 0.45;

    positions[i * 3] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;
    seeds[i] = Math.random();
    shells[i] = isShell ? 1 : 0;
    if (isShell && shellPts.length < 3000 * 3) shellPts.push(x, y, z);
  }

  const pointsGeo = new THREE.BufferGeometry();
  pointsGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  pointsGeo.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
  pointsGeo.setAttribute('aShell', new THREE.BufferAttribute(shells, 1));

  // Neural connections: random nearby cortex point pairs.
  const nShell = shellPts.length / 3;
  const linePos = new Float32Array(MAX_SEGMENTS * 2 * 3);
  const linePhase = new Float32Array(MAX_SEGMENTS * 2);
  const lineT = new Float32Array(MAX_SEGMENTS * 2);
  let seg = 0;
  for (let attempt = 0; attempt < 8000 && seg < MAX_SEGMENTS; attempt++) {
    const i = (Math.random() * nShell) | 0;
    const j = (Math.random() * nShell) | 0;
    if (i === j) continue;
    const ax = shellPts[i * 3]!;
    const ay = shellPts[i * 3 + 1]!;
    const az = shellPts[i * 3 + 2]!;
    const bx = shellPts[j * 3]!;
    const by = shellPts[j * 3 + 1]!;
    const bz = shellPts[j * 3 + 2]!;
    const d = Math.hypot(ax - bx, ay - by, az - bz);
    if (d < 0.18 || d > 0.55) continue;
    const base = seg * 6;
    linePos[base] = ax;
    linePos[base + 1] = ay;
    linePos[base + 2] = az;
    linePos[base + 3] = bx;
    linePos[base + 4] = by;
    linePos[base + 5] = bz;
    const phase = Math.random();
    linePhase[seg * 2] = phase;
    linePhase[seg * 2 + 1] = phase;
    lineT[seg * 2] = 0;
    lineT[seg * 2 + 1] = 1;
    seg += 1;
  }

  const linesGeo = new THREE.BufferGeometry();
  linesGeo.setAttribute(
    'position',
    new THREE.BufferAttribute(linePos.subarray(0, seg * 6), 3),
  );
  linesGeo.setAttribute(
    'aPhase',
    new THREE.BufferAttribute(linePhase.subarray(0, seg * 2), 1),
  );
  linesGeo.setAttribute(
    'aT',
    new THREE.BufferAttribute(lineT.subarray(0, seg * 2), 1),
  );

  return { pointsGeo, linesGeo };
}

function buildStarfield(): THREE.Points {
  const pos = new Float32Array(STARS * 3);
  for (let i = 0; i < STARS; i++) {
    const u = Math.random() * 2 - 1;
    const phi = Math.random() * Math.PI * 2;
    const s = Math.sqrt(1 - u * u);
    const r = 22 + Math.random() * 22;
    pos[i * 3] = s * Math.cos(phi) * r;
    pos[i * 3 + 1] = u * r;
    pos[i * 3 + 2] = s * Math.sin(phi) * r;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({
    color: 0x8899cc,
    size: 0.06,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.6,
    depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}
