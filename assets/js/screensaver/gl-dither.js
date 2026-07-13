/* === Screensaver Mode: GL Dither (WebGL2 GPU Bayer Dither — Multi-Pattern) === */

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

      var SIMPLEX_GLSL = [
        'vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}',
        'vec2 mod289v2(vec2 x){return x-floor(x*(1.0/289.0))*289.0;}',
        'vec3 permute(vec3 x){return mod289((x*34.0+1.0)*x);}',
        'float snoise(vec2 v){',
        '  const vec4 C=vec4(0.211324865405187,0.366025403784439,-0.577350269189626,0.024390243902439);',
        '  vec2 i=floor(v+dot(v,C.yy));',
        '  vec2 x0=v-i+dot(i,C.xx);',
        '  vec2 i1;i1=(x0.x>x0.y)?vec2(1.0,0.0):vec2(0.0,1.0);',
        '  vec4 x12=x0.xyxy+C.xxzz;x12.xy-=i1;',
        '  i=mod289v2(i);',
        '  vec3 p=permute(permute(i.y+vec3(0.0,i1.y,1.0))+i.x+vec3(0.0,i1.x,1.0));',
        '  vec3 m=max(0.5-vec3(dot(x0,x0),dot(x12.xy,x12.xy),dot(x12.zw,x12.zw)),0.0);',
        '  m=m*m;m=m*m;',
        '  vec3 x=2.0*fract(p*C.www)-1.0;',
        '  vec3 h=abs(x)-0.5;',
        '  vec3 ox=floor(x+0.5);',
        '  vec3 a0=x-ox;',
        '  m*=1.79284291400159-0.85373472095314*(a0*a0+h*h);',
        '  vec3 g;',
        '  g.x=a0.x*x0.x+h.x*x0.y;',
        '  g.yz=a0.yz*x12.xz+h.yz*x12.yw;',
        '  return 130.0*dot(m,g);',
        '}'
      ].join('\n');

      var FBM_GLSL = [
        'float fbm(vec2 p) {',
        '    float v = 0.0; float a = 0.5;',
        '    for (int i = 0; i < 3; i++) {',
        '        v += a * (snoise(p) * 0.5 + 0.5);',
        '        p *= 2.0; a *= 0.5;',
        '    }',
        '    return v;',
        '}'
      ].join('\n');

      var VORONOI_GLSL = [
        'vec2 hash2(vec2 p) {',
        '    p = vec2(dot(p,vec2(127.1,311.7)), dot(p,vec2(269.5,183.3)));',
        '    return fract(sin(p)*43758.5453);',
        '}',
        'float voronoiDist(vec2 uv, float t) {',
        '    vec2 ip = floor(uv);',
        '    vec2 fp = fract(uv);',
        '    float minDist = 1.0;',
        '    for (int y = -1; y <= 1; y++) {',
        '        for (int x = -1; x <= 1; x++) {',
        '            vec2 neighbor = vec2(float(x), float(y));',
        '            vec2 point = hash2(ip + neighbor);',
        '            point = 0.5 + 0.5*sin(t*0.5 + 6.2831*point);',
        '            float d = length(neighbor + point - fp);',
        '            minDist = min(minDist, d);',
        '        }',
        '    }',
        '    return minDist;',
        '}'
      ].join('\n');

      // --- Pattern-specific main() bodies ---
      // Each returns a gradient value computation (expects cellPos, t, u_resolution available)

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

      PATTERN_MAIN.fbm = [
        '    vec2 p = cellPos * 0.6;',
        '    vec2 wobble = vec2(sin(t*0.2)*0.4, cos(t*0.15)*0.4);',
        '    float n1 = fbm(p + wobble);',
        '    float n2 = fbm(p + vec2(3.1, 7.2) + wobble * 0.7);',
        '    vec2 warp = vec2(n1, n2) * 0.6;',
        '    float val = fbm(p + warp + vec2(cos(t*0.1)*0.3, sin(t*0.13)*0.3));'
      ].join('\n');

      PATTERN_MAIN.warp = [
        '    vec2 p = cellPos * 0.4;',
        '    vec2 wobble = vec2(sin(t*0.1)*0.6, cos(t*0.07)*0.6);',
        '    vec2 q = vec2(fbm(p + wobble), fbm(p + vec2(5.2, 1.3) + wobble*0.8));',
        '    vec2 wobble2 = vec2(cos(t*0.06)*0.4, sin(t*0.09)*0.4);',
        '    vec2 r = vec2(fbm(p + 2.5*q + vec2(1.7, 9.2) + wobble2), fbm(p + 2.5*q + vec2(8.3, 2.8) + wobble2*1.2));',
        '    float val = fbm(p + 2.5*r);'
      ].join('\n');

      PATTERN_MAIN['voronoi-trig'] = [
        '    vec2 vuv = cellPos * 2.0;',
        '    float minDist = voronoiDist(vuv, t);',
        '    float warpedX = cellPos.x + minDist * 0.6;',
        '    float warpedY = cellPos.y + minDist * 0.4;',
        '    float w1 = 0.5 + 0.5 * sin(warpedX * 12.0 - t * 0.8);',
        '    float w2 = 0.5 + 0.5 * sin(warpedY * 10.0 + t * 0.6);',
        '    float w3 = 0.5 + 0.5 * cos((warpedX + warpedY) * 8.0 - t * 0.4);',
        '    float val = w1 * 0.4 + w2 * 0.3 + w3 * 0.3;'
      ].join('\n');

      PATTERN_MAIN['trig-warp-reaction'] = [
        '    // Voronoi(0.7) + Warp(0.3) blend',
        '    float vd = voronoiDist(cellPos * 2.0, t);',
        '    vec2 p = cellPos * 0.4;',
        '    vec2 wobble = vec2(sin(t*0.1)*0.6, cos(t*0.07)*0.6);',
        '    vec2 q = vec2(fbm(p + wobble), fbm(p + vec2(5.2,1.3) + wobble*0.8));',
        '    vec2 wobble2 = vec2(cos(t*0.06)*0.4, sin(t*0.09)*0.4);',
        '    vec2 r = vec2(fbm(p + 2.5*q + vec2(1.7,9.2) + wobble2), fbm(p + 2.5*q + vec2(8.3,2.8) + wobble2*1.2));',
        '    float warpVal = fbm(p + 2.5*r);',
        '    float val = vd * 0.7 + warpVal * 0.3;'
      ].join('\n');

      // --- Determine which GLSL libs a pattern needs ---
      function patternNeedsSimplex(key) {
        return key !== 'trig';
      }
      function patternNeedsFBM(key) {
        return key === 'fbm' || key === 'warp' || key === 'trig-warp-reaction';
      }
      function patternNeedsVoronoi(key) {
        return key === 'voronoi-trig' || key === 'trig-warp-reaction';
      }

      // --- Build full fragment shader for a given pattern key ---
      function buildFragShader(patternKey) {
        var src = '#version 300 es\nprecision highp float;\n';
        src += 'uniform float u_time;\nuniform vec2 u_resolution;\nuniform vec3 u_accent;\nuniform vec3 u_palette[4];\n';
        src += 'out vec4 fragColor;\n\n';
        src += BAYER_GLSL + '\n\n';
        if (patternNeedsSimplex(patternKey)) src += SIMPLEX_GLSL + '\n\n';
        if (patternNeedsFBM(patternKey)) src += FBM_GLSL + '\n\n';
        if (patternNeedsVoronoi(patternKey)) src += VORONOI_GLSL + '\n\n';
        src += 'void main() {\n';
        src += '    vec2 uv = gl_FragCoord.xy / u_resolution;\n';
        src += '    float t = u_time * 0.4;\n';
        src += '    float cellSize = max(2.0, floor(min(u_resolution.x, u_resolution.y) / 400.0));\n';
        src += '    vec2 cellUv = floor(gl_FragCoord.xy / cellSize) * cellSize;\n';
        src += '    vec2 cellPos = cellUv / u_resolution;\n\n';
        src += PATTERN_MAIN[patternKey] + '\n\n';
        src += '    val = val * val;\n';
        src += '    float threshold = bayer8(gl_FragCoord.xy / cellSize);\n';
        src += '    bool on = val > threshold;\n';
        src += '    if (!on) { fragColor = vec4(0.0, 0.0, 0.0, 1.0); return; }\n\n';
        src += '    // Color from palette — smooth cubic interpolation\n';
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

      function glDitherInit() {
        var glCanvas = ssGetGLCanvas();
        glCanvas.width = window.innerWidth;
        glCanvas.height = window.innerHeight;
        var patternKey = ditherPattern || 'trig';
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
        var patternKey = ditherPattern || 'trig';
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
        if (instance) instance.render();
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
        var cell = Math.max(2, Math.floor(Math.min(w, h) / 80));
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
        gl: true
      };
    })();
