/* === Screensaver Mode: GL Noise (WebGL2 FBM) === */

    // Fullscreen fragment shader: animated FBM noise colored by accent/palette.
    // Uses HyperGL for all WebGL boilerplate.

    (function () {
      var NOISE_FRAG = [
        '#version 300 es',
        'precision highp float;',
        'uniform float u_time;',
        'uniform vec2 u_resolution;',
        'uniform vec3 u_accent;',
        'uniform vec3 u_palette[4];',
        'out vec4 fragColor;',
        '',
        '// Hash function for noise',
        'float hash(vec2 p) {',
        '    vec3 p3 = fract(vec3(p.xyx) * 0.1031);',
        '    p3 += dot(p3, p3.yzx + 33.33);',
        '    return fract((p3.x + p3.y) * p3.z);',
        '}',
        '',
        '// Value noise with smooth interpolation',
        'float noise(vec2 p) {',
        '    vec2 i = floor(p);',
        '    vec2 f = fract(p);',
        '    f = f * f * (3.0 - 2.0 * f);',
        '    float a = hash(i);',
        '    float b = hash(i + vec2(1.0, 0.0));',
        '    float c = hash(i + vec2(0.0, 1.0));',
        '    float d = hash(i + vec2(1.0, 1.0));',
        '    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);',
        '}',
        '',
        '// Fractal Brownian Motion — 5 octaves',
        'float fbm(vec2 p) {',
        '    float val = 0.0;',
        '    float amp = 0.5;',
        '    float freq = 1.0;',
        '    for (int i = 0; i < 5; i++) {',
        '        val += amp * noise(p * freq);',
        '        freq *= 2.0;',
        '        amp *= 0.5;',
        '        p += vec2(1.7, 9.2);',
        '    }',
        '    return val;',
        '}',
        '',
        'void main() {',
        '    vec2 uv = gl_FragCoord.xy / u_resolution;',
        '    float t = u_time * 0.15;',
        '',
        '    // Domain warp for organic movement',
        '    vec2 q = vec2(fbm(uv * 3.0 + t), fbm(uv * 3.0 + vec2(5.2, 1.3) + t * 0.7));',
        '    vec2 r = vec2(fbm(uv * 3.0 + q + vec2(1.7, 9.2) + t * 0.3),',
        '                  fbm(uv * 3.0 + q + vec2(8.3, 2.8) + t * 0.5));',
        '    float f = fbm(uv * 3.0 + r);',
        '',
        '    // Color using palette',
        '    float idx = f * 3.0;',
        '    int ci = int(min(floor(idx), 2.0));',
        '    float frac = fract(idx);',
        '    vec3 colA = (ci == 0) ? u_palette[0] : (ci == 1) ? u_palette[1] : u_palette[2];',
        '    vec3 colB = (ci == 0) ? u_palette[1] : (ci == 1) ? u_palette[2] : u_palette[3];',
        '    vec3 col = mix(colA, colB, frac);',
        '',
        '    // Darken edges and modulate brightness',
        '    float brightness = f * f * 1.2;',
        '    col *= brightness;',
        '',
        '    fragColor = vec4(col, 1.0);',
        '}'
      ].join('\n');

      var instance = null;

      function glNoiseInit() {
        var glCanvas = ssGetGLCanvas();
        glCanvas.width = window.innerWidth;
        glCanvas.height = window.innerHeight;
        // Reuse instance if context is still alive, else recreate
        if (!instance || !instance.gl || instance.gl.isContextLost()) {
          instance = HyperGL.create({
            target: glCanvas,
            fragment: NOISE_FRAG,
            loop: false
          });
        } else {
          instance.resize();
        }
      }

      function glNoiseDraw() {
        if (instance) instance.render();
      }

      function glNoiseResize() {
        if (instance) instance.resize();
      }

      function glNoiseCleanup() {
        // Don't destroy — keep the context alive for re-activation
        // The GL canvas persists across screensaver sessions
      }

      function glNoisePreview(ctx, w, h) {
        // Render a quick static preview using 2D canvas (simplified noise approximation)
        var imgData = ctx.createImageData(w, h);
        var data = imgData.data;
        var accent = ssGetAccent();
        var rgb = ssHexToRgb(accent);
        for (var y = 0; y < h; y++) {
          for (var x = 0; x < w; x++) {
            var nx = x / w * 4.0;
            var ny = y / h * 4.0;
            var val = (Math.sin(nx * 3.0 + ny * 2.0) * 0.5 + 0.5) *
                      (Math.cos(ny * 4.0 - nx * 1.5) * 0.5 + 0.5);
            val = val * val * 1.2;
            var idx = (y * w + x) * 4;
            data[idx] = Math.floor(rgb.r * val);
            data[idx + 1] = Math.floor(rgb.g * val);
            data[idx + 2] = Math.floor(rgb.b * val);
            data[idx + 3] = 255;
          }
        }
        ctx.putImageData(imgData, 0, 0);
      }

      ssModes['gl-noise'] = {
        init: glNoiseInit,
        draw: glNoiseDraw,
        resize: glNoiseResize,
        cleanup: glNoiseCleanup,
        preview: glNoisePreview,
        gl: true
      };
    })();
