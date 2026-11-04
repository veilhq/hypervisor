/* === Screensaver Mode: GL Dither (WebGL2 GPU Bayer Dither - Multi-Pattern) === */

    // GPU Bayer 8x8 ordered dithering with selectable gradient pattern.
    // Pattern is chosen via ditherPattern preference (engine head state).

    (function () {

      // --- Shared GLSL fragments ---
      var BAYER_GLSL = [
        'float bayer8(vec2 pos) {',
        '    ivec2 p = ivec2(mod(pos, 8.0));',
        '    float m[64] = float[64](',
        '         0.0, 32.0,  8.0, 40.0,  2.0, 34.0, 10.0, 42.0,',
        '        48.0, 16.0, 56.0, 24.0, 50.0, 18.0, 58.0, 26.0,',
        '        12.0, 44.0,  4.0, 36.0, 14.0, 46.0,  6.0, 38.0,',
        '        60.0, 28.0, 52.0, 20.0, 62.0, 30.0, 54.0, 22.0,',
        '         3.0, 35.0, 11.0, 43.0,  1.0, 33.0,  9.0, 41.0,',
        '        51.0, 19.0, 59.0, 27.0, 49.0, 17.0, 57.0, 25.0,',
        '        15.0, 47.0,  7.0, 39.0, 13.0, 45.0,  5.0, 37.0,',
        '        63.0, 31.0, 55.0, 23.0, 61.0, 29.0, 53.0, 21.0',
        '    );',
        '    return m[p.x + p.y * 8] / 64.0;',
        '}'
      ].join('\n');

      // Animated Voronoi edge distance (F2 - F1); only compiled for patterns
      // that list it in NEEDS_VORONOI.
      var VORONOI_GLSL = [
        'vec2 vorHash(vec2 p) {',
        '    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));',
        '    return fract(sin(p) * 43758.5453);',
        '}',
        '// xyzw = seam distance (F2 - F1), F1, hash of the winning cell.',
        'vec4 vorCell(vec2 x, float tm, float k) {',
        '    vec2 n = floor(x);',
        '    vec2 f = fract(x);',
        '    float d1 = 8.0;',
        '    float d2 = 8.0;',
        '    vec2 id = vec2(0.0);',
        '    for (int j = -1; j <= 1; j++) {',
        '        for (int i = -1; i <= 1; i++) {',
        '            vec2 g = vec2(float(i), float(j));',
        '            vec2 o = 0.5 + 0.5 * sin(tm + 6.2831853 * vorHash(n + g));',
        '            vec2 v = max(abs(g + o - f), 1e-5);',
        '            float d = pow(pow(v.x, k) + pow(v.y, k), 1.0 / k);',
        '            if (d < d1) { d2 = d1; d1 = d; id = vorHash(n + g); }',
        '            else if (d < d2) { d2 = d; }',
        '        }',
        '    }',
        '    return vec4(d2 - d1, d1, id);',
        '}',
        'float vorEdge(vec2 x, float tm, float k) {',
        '    return vorCell(x, tm, k).x;',
        '}'
      ].join('\n');
      var NEEDS_VORONOI = { seamfold: true, fracture: true };

      // 3D gradient noise plus a Musgrave ridged multifractal; only compiled
      // for patterns that list it in NEEDS_NOISE.
      var NOISE_GLSL = [
        'vec3 gHash(vec3 p) {',
        '    p = vec3(dot(p, vec3(127.1, 311.7, 74.7)),',
        '             dot(p, vec3(269.5, 183.3, 246.1)),',
        '             dot(p, vec3(113.5, 271.9, 124.6)));',
        '    return fract(sin(p) * 43758.5453) * 2.0 - 1.0;',
        '}',
        'float gNoise(vec3 x) {',
        '    vec3 i = floor(x);',
        '    vec3 f = fract(x);',
        '    vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);',
        '    float n000 = dot(gHash(i),                  f);',
        '    float n100 = dot(gHash(i + vec3(1,0,0)),    f - vec3(1,0,0));',
        '    float n010 = dot(gHash(i + vec3(0,1,0)),    f - vec3(0,1,0));',
        '    float n110 = dot(gHash(i + vec3(1,1,0)),    f - vec3(1,1,0));',
        '    float n001 = dot(gHash(i + vec3(0,0,1)),    f - vec3(0,0,1));',
        '    float n101 = dot(gHash(i + vec3(1,0,1)),    f - vec3(1,0,1));',
        '    float n011 = dot(gHash(i + vec3(0,1,1)),    f - vec3(0,1,1));',
        '    float n111 = dot(gHash(i + vec3(1,1,1)),    f - vec3(1,1,1));',
        '    return mix(mix(mix(n000, n100, u.x), mix(n010, n110, u.x), u.y),',
        '               mix(mix(n001, n101, u.x), mix(n011, n111, u.x), u.y), u.z);',
        '}',
        'float ridgedMF(vec3 p) {',
        '    float sum = 0.0;',
        '    float norm = 0.0;',
        '    float amp = 1.0;',
        '    float weight = 1.0;',
        '    for (int i = 0; i < 4; i++) {',
        '        float n = 1.0 - abs(gNoise(p) * 1.4);',
        '        n = n * n * weight;',
        '        weight = clamp(n * 2.0, 0.0, 1.0);',
        '        sum += n * amp;',
        '        norm += amp;',
        '        amp *= 0.5;',
        '        p = p * 2.03 + vec3(17.1, 9.2, 3.7);',
        '    }',
        '    return sum / norm;',
        '}'
      ].join('\n');
      var NEEDS_NOISE = { iris: true, fracture: true };

      // --- Pattern-specific main() bodies ---
      // Each computes a float `val` from the continuous fields available in
      // main(): cellPos (0..1 cell center), cellUv (pixel coords), t (time).
      // Every pattern is a closed-form sinusoidal/distance field - no hash
      // lattice - so nothing aliases against the Bayer grid and the output
      // flows without visible tiling.

      var PATTERN_MAIN = {};

      PATTERN_MAIN.trig = [
        '    float cx = 0.5 + sin(t * 0.4) * 0.3;',
        '    float cy = 0.5 + cos(t * 0.3) * 0.3;',
        '    vec2 d = cellPos - vec2(cx, cy);',
        '    float dist = length(d);',
        '    float g1 = 0.5 + 0.5 * sin(dist * 6.0 - t * 0.8);',
        '    float g2 = 0.5 + 0.5 * sin((cellUv.x + cellUv.y) * 0.0032 + t * 0.5);',
        '    float g3 = 0.5 + 0.5 * cos((cellUv.y - cellUv.x) * 0.0041 - t * 0.3);',
        '    float val = g1 * 0.5 + g2 * 0.25 + g3 * 0.25;'
      ].join('\n');

      PATTERN_MAIN.interference = [
        '    // Three radial wave emitters drifting on slow orbits; their',
        '    // overlapping ripples interfere into a living moire.',
        '    // Cropped 3.3x into the field so the ripples read large.',
        '    vec2 zp = (cellPos - 0.5) / 3.3 + 0.5;',
        '    vec2 s1 = vec2(0.3 + sin(t*0.23)*0.2, 0.5 + cos(t*0.19)*0.25);',
        '    vec2 s2 = vec2(0.7 + cos(t*0.17)*0.2, 0.4 + sin(t*0.27)*0.25);',
        '    vec2 s3 = vec2(0.5 + sin(t*0.13)*0.3, 0.6 + cos(t*0.21)*0.2);',
        '    float w1 = sin(length(zp - s1) * 34.0 - t * 1.1);',
        '    float w2 = sin(length(zp - s2) * 28.0 - t * 0.9);',
        '    float w3 = sin(length(zp - s3) * 40.0 - t * 1.3);',
        '    float val = 0.5 + 0.16 * (w1 + w2 + w3);'
      ].join('\n');

      PATTERN_MAIN.plasma = [
        '    // Classic demoscene plasma - summed sinusoids in x, y, and radial',
        '    // space around a drifting center.',
        '    float v = 0.0;',
        '    v += sin(cellPos.x * 10.0 + t);',
        '    v += sin((cellPos.y * 10.0 + t) * 0.8);',
        '    v += sin((cellPos.x + cellPos.y) * 10.0 + t * 0.6);',
        '    float cx = cellPos.x + 0.5 * sin(t * 0.33);',
        '    float cy = cellPos.y + 0.5 * cos(t * 0.41);',
        '    v += sin(sqrt(cx*cx + cy*cy) * 14.0 + t);',
        '    float val = 0.5 + 0.125 * v;'
      ].join('\n');

      PATTERN_MAIN.swirl = [
        '    // Polar warp around a drifting center - angle feeds a spiral,',
        '    // radius feeds concentric rings. Reads as a slow vortex.',
        '    // Cropped 3.3x into the field for a tighter vortex.',
        '    vec2 zp = (cellPos - 0.5) / 3.3 + 0.5;',
        '    vec2 c = vec2(0.5 + sin(t*0.15)*0.2, 0.5 + cos(t*0.12)*0.2);',
        '    vec2 d = zp - c;',
        '    float r = length(d);',
        '    float a = atan(d.y, d.x);',
        '    float spiral = sin(a * 3.0 + r * 18.0 - t * 1.2);',
        '    float rings  = sin(r * 22.0 - t * 0.7);',
        '    float val = 0.5 + 0.25 * (spiral * 0.6 + rings * 0.4);'
      ].join('\n');

      PATTERN_MAIN.lissajous = [
        '    // Two orthogonal standing-wave families with incommensurate',
        '    // frequencies - weaves a drifting plaid that never closes a period.',
        '    // Cropped 3.3x into the field so the weave reads large.',
        '    vec2 zp = (cellPos - 0.5) / 3.3 + 0.5;',
        '    float a = sin(zp.x * 18.0 + sin(t*0.3)*2.0);',
        '    float b = sin(zp.y * 23.0 + cos(t*0.27)*2.0);',
        '    float cz = sin((zp.x*13.0 + zp.y*11.0) + t*0.5);',
        '    float val = 0.5 + 0.166 * (a + b + cz);'
      ].join('\n');

      PATTERN_MAIN.tunnel = [
        '    // Polar 1/r depth scroll - reads as infinite flight down a',
        '    // textured tube. Angular spokes add rotational structure.',
        '    vec2 p = cellPos - 0.5;',
        '    p.x *= u_resolution.x / u_resolution.y;',
        '    float r = length(p);',
        '    float a = atan(p.y, p.x);',
        '    float depth = 0.30 / (r + 0.08) + t * 0.6;',
        '    float rib = 0.5 + 0.5 * sin(depth * 6.2831);',
        '    float spokes = 0.5 + 0.5 * sin(a * 8.0 + t * 0.5);',
        '    float val = rib * 0.65 + spokes * 0.35;'
      ].join('\n');

      PATTERN_MAIN.kaleidoscope = [
        '    // Center-anchored kaleidoscope: angle folded into mirrored wedges,',
        '    // over a 1/r depth scroll. The wall is textured by an interference',
        '    // stack - several wavefronts at incommensurate frequencies with',
        '    // independently drifting phases, in (angle, depth) space. Their',
        '    // crests form a lattice-free moire that streams toward the viewer',
        '    // and never repeats. Thresholded thin to stay sparse.',
        '    vec2 p = cellPos - 0.5;',
        '    p.x *= u_resolution.x / u_resolution.y;',
        '    float r = length(p);',
        '    float a = atan(p.y, p.x);',
        '    // Mirror-fold the angle into N wedges (kaleidoscope symmetry).',
        '    float wedges = 6.0;',
        '    float seg = 6.2831853 / wedges;',
        '    a = abs(mod(a, seg) - seg * 0.5);',
        '    // Depth scroll - texture streams down the tube toward the viewer.',
        '    float depth = 0.30 / (r + 0.08) + t * 0.6;',
        '    // Interference stack over (foldedAngle, depth). Incommensurate',
        '    // frequencies + independently drifting phases = non-repeating moire.',
        '    float aw = a * 7.0;',
        '    float f1 = sin(depth * 5.0  + aw * 1.0 + t * 0.7);',
        '    float f2 = sin(depth * 8.3  - aw * 1.7 + t * 0.5);',
        '    float f3 = sin(depth * 3.1  + aw * 2.3 - t * 0.4);',
        '    float f4 = sin(depth * 11.7 - aw * 0.6 + t * 0.9);',
        '    // Sum folds the crests into a moire; gentle power lifts midtones',
        '    // while staying in 0..1 so the dither keeps its stippled gradient',
        '    // (no full-fill clipping).',
        '    float sum = (f1 + f2 + f3 + f4) * 0.25;',
        '    float wall = pow(0.5 + 0.5 * sum, 1.3);',
        '    // Depth falloff (#4): fade toward the central vanishing point.',
        '    float falloff = smoothstep(0.0, 0.12, r);',
        '    float val = wall * falloff;'
      ].join('\n');

      PATTERN_MAIN.inkfold = [
        '    // Six-fold radial inkblot. Interference stack gives the organic,',
        '    // non-repeating base (lattice-free); borrowed from the Rorschach',
        '    // mode: angular lobe harmonics for complex lobe shapes, and a hard',
        '    // threshold that turns the smooth field into solid ink masses with',
        '    // sparse negative space - the inkblot read, not a smooth gradient.',
        '    vec2 p = cellPos - 0.5;',
        '    p.x *= u_resolution.x / u_resolution.y;',
        '    float r = length(p);',
        '    float a = atan(p.y, p.x);',
        '    // Mirror-fold the angle into 6 wedges (radial symmetry).',
        '    float wedges = 6.0;',
        '    float seg = 6.2831853 / wedges;',
        '    a = abs(mod(a, seg) - seg * 0.5);',
        '    // Depth scroll - texture streams down the tube toward the viewer.',
        '    float depth = 0.30 / (r + 0.08) + t * 0.6;',
        '    // Interference stack over (foldedAngle, depth) - the organic base.',
        '    float aw = a * 7.0;',
        '    float f1 = sin(depth * 5.0  + aw * 1.0 + t * 0.7);',
        '    float f2 = sin(depth * 8.3  - aw * 1.7 + t * 0.5);',
        '    float f3 = sin(depth * 3.1  + aw * 2.3 - t * 0.4);',
        '    float f4 = sin(depth * 11.7 - aw * 0.6 + t * 0.9);',
        '    float field = (f1 + f2 + f3 + f4) * 0.25;',
        '    // Angular lobe harmonics (Rorschach): multiple harmonics of the',
        '    // folded angle add complex, breathing lobe shapes to the blot edge.',
        '    float lobes = 0.22 * sin(a * 2.0 + t * 0.3)',
        '                + 0.18 * sin(a * 5.0 - t * 0.2)',
        '                + 0.12 * sin(a * 9.0 + t * 0.4);',
        '    float v = 0.5 + 0.5 * field + lobes;',
        '    // Inverted Rorschach: the blot shape is punched OUT as negative',
        '    // space (voids), and the surrounding field is the dithered texture.',
        '    // (1.0 - mask) flips ink and ground. Interior kept mid-range so the',
        '    // downstream val*val squaring does not blow it out to solid.',
        '    float mask = smoothstep(0.46, 0.58, v);',
        '    float wall = (1.0 - mask) * (0.15 + 0.4 * clamp(v, 0.0, 1.0));',
        '    // Depth falloff (#4): fade toward the central vanishing point.',
        '    float falloff = smoothstep(0.0, 0.12, r);',
        '    float val = wall * falloff;'
      ].join('\n');

      PATTERN_MAIN.seamfold = [
        '    // Kaleidoscope tunnel walls textured with a shifting Voronoi; only',
        '    // the cell seams are lit, the cell interiors stay dark.',
        '    vec2 p = cellPos - 0.5;',
        '    p.x *= u_resolution.x / u_resolution.y;',
        '    float r = length(p);',
        '    float a = atan(p.y, p.x);',
        '    float wedges = 6.0;',
        '    float seg = 6.2831853 / wedges;',
        '    a = abs(mod(a, seg) - seg * 0.5);',
        '    float depth = 0.30 / (r + 0.08) + t * 0.6;',
        '    vec2 q = vec2(a * 4.6, depth * 1.7);',
        '    // Minkowski exponent: 1 = diamond cells, 2 = round, high = squarish.',
        '    // Drifts slowly so the cell shape breathes between the three.',
        '    float k = 2.5 + 1.5 * sin(t * 0.35);',
        '    float e = vorEdge(q, t * 1.6, k);',
        '    // Bright core plus a wide soft halo so the seams bloom into the dark.',
        '    float core = 1.0 - smoothstep(0.0, 0.14, e);',
        '    // Halo is offset so it hits exactly 0 away from the seams; any',
        '    // positive value would light the Bayer threshold-0 cell everywhere.',
        '    float halo = max(exp(-e * 48.0) - 0.02, 0.0);',
        '    float wall = 0.72 * clamp(core + 0.5 * halo, 0.0, 1.0);',
        '    float falloff = smoothstep(0.0, 0.12, r);',
        '    float val = wall * falloff;'
      ].join('\n');

      PATTERN_MAIN.iris = [
        '    // Kaleidoscope tunnel walls veined by a ridged multifractal; only',
        '    // the ridge crests are lit, everything below the cutoff is black.',
        '    vec2 p = cellPos - 0.5;',
        '    p.x *= u_resolution.x / u_resolution.y;',
        '    float r = length(p);',
        '    float a = atan(p.y, p.x);',
        '    float wedges = 6.0;',
        '    float seg = 6.2831853 / wedges;',
        '    a = abs(mod(a, seg) - seg * 0.5);',
        '    float depth = 0.30 / (r + 0.08) + t * 0.6;',
        '    float ridge = ridgedMF(vec3(a * 4.0, depth * 1.4, t * 0.5));',
        '    // Remap above a hard cutoff so the dark ground is exactly 0.',
        '    float vein = clamp((ridge - 0.42) / 0.58, 0.0, 1.0);',
        '    float wall = 0.8 * pow(vein, 1.4);',
        '    float falloff = smoothstep(0.0, 0.12, r);',
        '    float val = wall * falloff;'
      ].join('\n');

      PATTERN_MAIN.fracture = [
        '    // Ridged-noise veins broken up by a shifting Voronoi: each cell',
        '    // samples a different patch of the noise, so veins snap at cell',
        '    // seams like cracked ice, with the seams themselves faintly lit.',
        '    vec2 p = cellPos - 0.5;',
        '    p.x *= u_resolution.x / u_resolution.y;',
        '    float r = length(p);',
        '    float a = atan(p.y, p.x);',
        '    float wedges = 6.0;',
        '    float seg = 6.2831853 / wedges;',
        '    a = abs(mod(a, seg) - seg * 0.5);',
        '    float depth = 0.30 / (r + 0.08) + t * 0.6;',
        '    float k = 2.5 + 1.5 * sin(t * 0.35);',
        '    vec4 vc = vorCell(vec2(a * 3.2, depth * 1.1), t * 1.2, k);',
        '    // Per-cell offset breaks the veins at seams; F1 bends them inside.',
        '    vec2 q = vec2(a * 4.0, depth * 1.4) + vc.zw * 7.0 + vc.y * 0.8;',
        '    float ridge = ridgedMF(vec3(q, t * 0.5));',
        '    float vein = clamp((ridge - 0.42) / 0.58, 0.0, 1.0);',
        '    float seam = 1.0 - smoothstep(0.0, 0.08, vc.x);',
        '    // Both terms hit exactly 0 away from veins and seams (Bayer',
        '    // threshold-0 cell would otherwise speckle the dark ground).',
        '    float wall = 0.8 * pow(vein, 1.4) + 0.35 * seam;',
        '    float falloff = smoothstep(0.0, 0.12, r);',
        '    float val = wall * falloff;'
      ].join('\n');

      PATTERN_MAIN.phasefold = [
        '    // Kaleidoscope with phase-modulated interference: slow modulator',
        '    // waves are fed into each wavefront\'s phase instead of summed, so',
        '    // crests bend and flow like liquid rather than crossing as moire.',
        '    vec2 p = cellPos - 0.5;',
        '    p.x *= u_resolution.x / u_resolution.y;',
        '    float r = length(p);',
        '    float a = atan(p.y, p.x);',
        '    float wedges = 6.0;',
        '    float seg = 6.2831853 / wedges;',
        '    a = abs(mod(a, seg) - seg * 0.5);',
        '    float depth = 0.30 / (r + 0.08) + t * 0.6;',
        '    float aw = a * 7.0;',
        '    // Slow modulators that bend the carrier waves.',
        '    float m1 = sin(aw * 2.0 + t * 0.4);',
        '    float m2 = sin(depth * 2.3 - t * 0.3);',
        '    float m3 = sin(depth * 1.7 + aw * 0.9 + t * 0.2);',
        '    float f1 = sin(depth * 5.0  + aw * 1.0 + 1.6 * m1 + t * 0.7);',
        '    float f2 = sin(depth * 8.3  - aw * 1.7 + 1.2 * m2 + t * 0.5);',
        '    float f3 = sin(depth * 3.1  + aw * 2.3 + 1.4 * m3 - t * 0.4);',
        '    float f4 = sin(depth * 11.7 - aw * 0.6 + 0.9 * m1 + t * 0.9);',
        '    float sum = (f1 + f2 + f3 + f4) * 0.25;',
        '    float wall = pow(0.5 + 0.5 * sum, 1.3);',
        '    float falloff = smoothstep(0.0, 0.12, r);',
        '    float val = wall * falloff;'
      ].join('\n');

      PATTERN_MAIN.logzoom = [
        '    // Kaleidoscope with log-polar depth: depth = -log(r) instead of',
        '    // 1/r, so the zoom runs at a constant rate and repeats in scale -',
        '    // an endless inward zoom rather than a tube that rushes at the edges.',
        '    vec2 p = cellPos - 0.5;',
        '    p.x *= u_resolution.x / u_resolution.y;',
        '    float r = length(p);',
        '    float a = atan(p.y, p.x);',
        '    float wedges = 6.0;',
        '    float seg = 6.2831853 / wedges;',
        '    a = abs(mod(a, seg) - seg * 0.5);',
        '    // 0.6 scale keeps the depth span close to the 1/r tunnel on screen;',
        '    // max() guards log(0) at the exact center.',
        '    float depth = -0.6 * log(max(r, 1e-4)) + t * 0.6;',
        '    float aw = a * 7.0;',
        '    float f1 = sin(depth * 5.0  + aw * 1.0 + t * 0.7);',
        '    float f2 = sin(depth * 8.3  - aw * 1.7 + t * 0.5);',
        '    float f3 = sin(depth * 3.1  + aw * 2.3 - t * 0.4);',
        '    float f4 = sin(depth * 11.7 - aw * 0.6 + t * 0.9);',
        '    float sum = (f1 + f2 + f3 + f4) * 0.25;',
        '    float wall = pow(0.5 + 0.5 * sum, 1.3);',
        '    float falloff = smoothstep(0.0, 0.12, r);',
        '    float val = wall * falloff;'
      ].join('\n');

      // --- All patterns are closed-form fields using only built-in GLSL
      //     (sin/cos/length/atan) - no helper libs to gate in. ---
      function buildFragShader(patternKey) {
        var src = '#version 300 es\nprecision highp float;\n';
        src += 'uniform float u_time;\nuniform vec2 u_resolution;\nuniform vec3 u_accent;\nuniform vec3 u_palette[4];\n';
        src += 'out vec4 fragColor;\n\n';
        src += BAYER_GLSL + '\n\n';
        if (NEEDS_VORONOI[patternKey]) src += VORONOI_GLSL + '\n\n';
        if (NEEDS_NOISE[patternKey]) src += NOISE_GLSL + '\n\n';        src += 'void main() {\n';
        src += '    vec2 uv = gl_FragCoord.xy / u_resolution;\n';
        src += '    float t = u_time * 0.4;\n';
        src += '    float cellSize = max(2.0, floor(min(u_resolution.x, u_resolution.y) / 650.0));\n';
        src += '    vec2 cellUv = floor(gl_FragCoord.xy / cellSize) * cellSize;\n';
        src += '    vec2 cellPos = cellUv / u_resolution;\n\n';
        src += PATTERN_MAIN[patternKey] + '\n\n';
        src += '    val = val * val;\n';
        src += '    float threshold = bayer8(gl_FragCoord.xy / cellSize);\n';
        src += '    bool on = val > threshold;\n';
        src += '    if (!on) { fragColor = vec4(0.0, 0.0, 0.0, 1.0); return; }\n\n';
        src += '    // Color from palette - smooth cubic interpolation\n';
        src += '    float pos = clamp(val, 0.0, 1.0) * 3.0;\n';
        src += '    float frac = smoothstep(0.0, 1.0, fract(pos));\n';
        src += '    int ci = int(min(floor(pos), 2.0));\n';
        src += '    vec3 colA = (ci == 0) ? u_palette[0] : (ci == 1) ? u_palette[1] : u_palette[2];\n';
        src += '    vec3 colB = (ci == 0) ? u_palette[1] : (ci == 1) ? u_palette[2] : u_palette[3];\n';
        src += '    vec3 col = mix(colA, colB, frac);\n';
        src += '    fragColor = vec4(col * 0.78, 1.0);\n';
        src += '}\n';
        return src;
      }

      // --- Instance management ---
      var instance = null;
      var compiledPattern = null;
      // Random time offset chosen on each activation so the field opens on a
      // different frame every time instead of always starting at t = 0.
      var timeSeed = 0;
      var startMs = 0;

      function glDitherInit() {
        timeSeed = Math.random() * 1000;
        startMs = performance.now();
        var glCanvas = ssGetGLCanvas();
        glCanvas.width = window.innerWidth;
        glCanvas.height = window.innerHeight;
        var patternKey = (window.__ss && window.__ss.ditherPattern) || 'trig';
        if (!PATTERN_MAIN[patternKey]) patternKey = 'trig';

        if (!instance || !instance.gl || instance.gl.isContextLost() || compiledPattern !== patternKey) {
          var frag = buildFragShader(patternKey);
          instance = HyperGL.create({
            target: glCanvas,
            fragment: frag,
            loop: false
          });
          compiledPattern = patternKey;
        } else {
          instance.resize();
        }
      }

      function glDitherDraw() {
        // Hot-swap if pattern changed while active
        var patternKey = (window.__ss && window.__ss.ditherPattern) || 'trig';
        if (!PATTERN_MAIN[patternKey]) patternKey = 'trig';
        if (compiledPattern !== patternKey) {
          var glCanvas = ssGetGLCanvas();
          var frag = buildFragShader(patternKey);
          instance = HyperGL.create({
            target: glCanvas,
            fragment: frag,
            loop: false
          });
          compiledPattern = patternKey;
        }
        if (instance) instance.render(timeSeed + (performance.now() - startMs) / 1000);
      }

      function glDitherResize() {
        if (instance) instance.resize();
      }

      function glDitherCleanup() {
        // Keep context alive for re-activation
      }

      function glDitherPreview(ctx, w, h) {
        var accent = ssGetAccent();
        var rgb = ssHexToRgb(accent);
        var imgData = ctx.createImageData(w, h);
        var data = imgData.data;
        var cell = Math.max(2, Math.floor(Math.min(w, h) / 130));
        var bayer = [
          [0, 32, 8, 40, 2, 34, 10, 42],
          [48, 16, 56, 24, 50, 18, 58, 26],
          [12, 44, 4, 36, 14, 46, 6, 38],
          [60, 28, 52, 20, 62, 30, 54, 22],
          [3, 35, 11, 43, 1, 33, 9, 41],
          [51, 19, 59, 27, 49, 17, 57, 25],
          [15, 47, 7, 39, 13, 45, 5, 37],
          [63, 31, 55, 23, 61, 29, 53, 21]
        ];
        var cols = Math.ceil(w / cell);
        var rows = Math.ceil(h / cell);
        for (var row = 0; row < rows; row++) {
          for (var col = 0; col < cols; col++) {
            var px = col * cell;
            var py = row * cell;
            var dx = (px - w * 0.5) / w;
            var dy = (py - h * 0.5) / h;
            var dist = Math.sqrt(dx * dx + dy * dy);
            var val = 0.5 + 0.5 * Math.sin(dist * 6);
            val = val * val;
            var threshold = bayer[row & 7][col & 7] / 64;
            var on = val > threshold;
            for (var sy = 0; sy < cell && py + sy < h; sy++) {
              for (var sx = 0; sx < cell && px + sx < w; sx++) {
                var idx = ((py + sy) * w + (px + sx)) * 4;
                data[idx] = on ? rgb.r : 0;
                data[idx + 1] = on ? rgb.g : 0;
                data[idx + 2] = on ? rgb.b : 0;
                data[idx + 3] = on ? 200 : 0;
              }
            }
          }
        }
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, w, h);
        ctx.putImageData(imgData, 0, 0);
      }

      ssModes['gl-dither'] = {
        init: glDitherInit,
        draw: glDitherDraw,
        resize: glDitherResize,
        cleanup: glDitherCleanup,
        preview: glDitherPreview,
        gl: true,
        meta: { name: "GL Dither", icon: "scan-line", desc: "Bayer dither on the GPU - silky smooth at any resolution" }
      };
    })();
