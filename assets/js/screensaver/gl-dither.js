/* === Screensaver Mode: GL Dither (WebGL2 GPU Bayer Dither) === */

    // GPU port of the existing CPU dither mode.
    // Bayer 8x8 ordered dithering with animated gradient fields — runs entirely
    // as a fragment shader, replacing per-pixel ImageData manipulation.

    (function () {
      var DITHER_FRAG = [
        '#version 300 es',
        'precision highp float;',
        'uniform float u_time;',
        'uniform vec2 u_resolution;',
        'uniform vec3 u_accent;',
        'uniform vec3 u_palette[4];',
        'out vec4 fragColor;',
        '',
        '// Bayer 8x8 dither matrix (normalized 0-1)',
        'float bayer8(vec2 pos) {',
        '    ivec2 p = ivec2(mod(pos, 8.0));',
        '    int idx = p.x + p.y * 8;',
        '    // Encode 8x8 Bayer matrix as bit operations',
        '    int x = p.x ^ p.y;',
        '    int v = ((p.y & 4) >> 1) | ((p.y & 2) << 1) | ((p.y & 1) << 3);',
        '    v |= ((x & 4) >> 2) | ((x & 2)) | ((x & 1) << 2);',
        '    // Alternative: direct computation matching the classic matrix',
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
        '    return m[idx] / 64.0;',
        '}',
        '',
        'void main() {',
        '    vec2 uv = gl_FragCoord.xy / u_resolution;',
        '    float t = u_time * 0.4;',
        '',
        '    // Cell size — match CPU version logic',
        '    float cellSize = max(2.0, floor(min(u_resolution.x, u_resolution.y) / 400.0));',
        '    vec2 cellUv = floor(gl_FragCoord.xy / cellSize) * cellSize;',
        '    vec2 cellPos = cellUv / u_resolution;',
        '',
        '    // Animated gradient fields (matching CPU version)',
        '    float cx = 0.5 + sin(t * 0.4) * 0.3;',
        '    float cy = 0.5 + cos(t * 0.3) * 0.3;',
        '    vec2 d = cellPos - vec2(cx, cy);',
        '    float dist = length(d);',
        '',
        '    float g1 = 0.5 + 0.5 * sin(dist * 6.0 - t * 0.8);',
        '    float g2 = 0.5 + 0.5 * sin((cellUv.x + cellUv.y) * 0.0032 + t * 0.5);',
        '    float g3 = 0.5 + 0.5 * cos((cellUv.y - cellUv.x) * 0.0041 - t * 0.3);',
        '    float val = g1 * 0.5 + g2 * 0.25 + g3 * 0.25;',
        '    val = val * val;',
        '',
        '    // Bayer threshold',
        '    float threshold = bayer8(gl_FragCoord.xy / cellSize);',
        '    bool on = val > threshold;',
        '',
        '    if (!on) {',
        '        fragColor = vec4(0.0, 0.0, 0.0, 1.0);',
        '        return;',
        '    }',
        '',
        '    // Color from palette (interpolate based on raw value)',
        '    float rawVal = g1 * 0.5 + g2 * 0.25 + g3 * 0.25;',
        '    float pos = rawVal * 3.0;',
        '    int ci = int(min(floor(pos), 2.0));',
        '    float frac = fract(pos);',
        '    vec3 colA = (ci == 0) ? u_palette[0] : (ci == 1) ? u_palette[1] : u_palette[2];',
        '    vec3 colB = (ci == 0) ? u_palette[1] : (ci == 1) ? u_palette[2] : u_palette[3];',
        '    vec3 col = mix(colA, colB, frac);',
        '',
        '    fragColor = vec4(col * 0.78, 1.0);',
        '}'
      ].join('\n');

      var instance = null;

      function glDitherInit() {
        var glCanvas = ssGetGLCanvas();
        glCanvas.width = window.innerWidth;
        glCanvas.height = window.innerHeight;
        if (!instance || !instance.gl || instance.gl.isContextLost()) {
          instance = HyperGL.create({
            target: glCanvas,
            fragment: DITHER_FRAG,
            loop: false
          });
        } else {
          instance.resize();
        }
      }

      function glDitherDraw() {
        if (instance) instance.render();
      }

      function glDitherResize() {
        if (instance) instance.resize();
      }

      function glDitherCleanup() {
        // Keep context alive for re-activation
      }

      function glDitherPreview(ctx, w, h) {
        // Use the CPU dither's preview logic (simplified)
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
