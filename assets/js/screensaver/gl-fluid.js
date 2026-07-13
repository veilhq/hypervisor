/* === Screensaver Mode: GL Fluid (WebGL2 Navier-Stokes) === */

    // GPU fluid simulation: splat → advect → divergence → pressure → gradient → render
    // Full incompressible Navier-Stokes with Jacobi pressure solve for realistic swirling.

    (function () {

      var VERT = '#version 300 es\n' +
        'void main() {\n' +
        '    float x = float(gl_VertexID % 2) * 4.0 - 1.0;\n' +
        '    float y = float(gl_VertexID / 2) * 4.0 - 1.0;\n' +
        '    gl_Position = vec4(x, y, 0.0, 1.0);\n' +
        '}\n';

      var ADVECT_FRAG = '#version 300 es\n' +
        'precision highp float;\n' +
        'uniform sampler2D u_vel;\n' +
        'uniform sampler2D u_source;\n' +
        'uniform vec2 u_texel;\n' +
        'uniform float u_dt;\n' +
        'uniform float u_dissipation;\n' +
        'out vec4 fragColor;\n' +
        'void main() {\n' +
        '    vec2 uv = gl_FragCoord.xy * u_texel;\n' +
        '    vec2 vel = texture(u_vel, uv).xy;\n' +
        '    vec2 pos = uv - vel * u_dt;\n' +
        '    pos = clamp(pos, u_texel, 1.0 - u_texel);\n' +
        '    fragColor = texture(u_source, pos) * u_dissipation;\n' +
        '}\n';

      var SPLAT_FRAG = '#version 300 es\n' +
        'precision highp float;\n' +
        'uniform sampler2D u_state;\n' +
        'uniform vec2 u_texel;\n' +
        'uniform vec2 u_point;\n' +
        'uniform vec3 u_value;\n' +
        'uniform float u_radius;\n' +
        'out vec4 fragColor;\n' +
        'void main() {\n' +
        '    vec2 uv = gl_FragCoord.xy * u_texel;\n' +
        '    vec4 s = texture(u_state, uv);\n' +
        '    vec2 d = uv - u_point;\n' +
        '    float dist = dot(d,d);\n' +
        '    float str = exp(-dist / u_radius);\n' +
        '    str *= str;\n' +
        '    s.xyz += u_value * str;\n' +
        '    fragColor = s;\n' +
        '}\n';

      var DIVERGENCE_FRAG = '#version 300 es\n' +
        'precision highp float;\n' +
        'uniform sampler2D u_vel;\n' +
        'uniform vec2 u_texel;\n' +
        'out vec4 fragColor;\n' +
        'void main() {\n' +
        '    vec2 uv = gl_FragCoord.xy * u_texel;\n' +
        '    float R = texture(u_vel, uv + vec2(u_texel.x, 0.0)).x;\n' +
        '    float L = texture(u_vel, uv - vec2(u_texel.x, 0.0)).x;\n' +
        '    float T = texture(u_vel, uv + vec2(0.0, u_texel.y)).y;\n' +
        '    float B = texture(u_vel, uv - vec2(0.0, u_texel.y)).y;\n' +
        '    fragColor = vec4(0.5 * (R - L + T - B), 0.0, 0.0, 1.0);\n' +
        '}\n';

      var CURL_FRAG = '#version 300 es\n' +
        'precision highp float;\n' +
        'uniform sampler2D u_vel;\n' +
        'uniform vec2 u_texel;\n' +
        'out vec4 fragColor;\n' +
        'void main() {\n' +
        '    vec2 uv = gl_FragCoord.xy * u_texel;\n' +
        '    float R = texture(u_vel, uv + vec2(u_texel.x, 0.0)).y;\n' +
        '    float L = texture(u_vel, uv - vec2(u_texel.x, 0.0)).y;\n' +
        '    float T = texture(u_vel, uv + vec2(0.0, u_texel.y)).x;\n' +
        '    float B = texture(u_vel, uv - vec2(0.0, u_texel.y)).x;\n' +
        '    fragColor = vec4((R - L) - (T - B), 0.0, 0.0, 1.0);\n' +
        '}\n';

      var VORTICITY_FRAG = '#version 300 es\n' +
        'precision highp float;\n' +
        'uniform sampler2D u_vel;\n' +
        'uniform sampler2D u_curl;\n' +
        'uniform vec2 u_texel;\n' +
        'uniform float u_strength;\n' +
        'out vec4 fragColor;\n' +
        'void main() {\n' +
        '    vec2 uv = gl_FragCoord.xy * u_texel;\n' +
        '    float cR = abs(texture(u_curl, uv + vec2(u_texel.x, 0.0)).x);\n' +
        '    float cL = abs(texture(u_curl, uv - vec2(u_texel.x, 0.0)).x);\n' +
        '    float cT = abs(texture(u_curl, uv + vec2(0.0, u_texel.y)).x);\n' +
        '    float cB = abs(texture(u_curl, uv - vec2(0.0, u_texel.y)).x);\n' +
        '    float c = texture(u_curl, uv).x;\n' +
        '    vec2 force = vec2(cT - cB, cL - cR);\n' +
        '    float len = length(force) + 0.00001;\n' +
        '    force = force / len * c * u_strength;\n' +
        '    vec4 v = texture(u_vel, uv);\n' +
        '    v.xy += force;\n' +
        '    v.xy = clamp(v.xy, -15.0, 15.0);\n' +
        '    fragColor = v;\n' +
        '}\n';

      var PRESSURE_FRAG = '#version 300 es\n' +
        'precision highp float;\n' +
        'uniform sampler2D u_pressure;\n' +
        'uniform sampler2D u_divergence;\n' +
        'uniform vec2 u_texel;\n' +
        'out vec4 fragColor;\n' +
        'void main() {\n' +
        '    vec2 uv = gl_FragCoord.xy * u_texel;\n' +
        '    float R = texture(u_pressure, uv + vec2(u_texel.x, 0.0)).x;\n' +
        '    float L = texture(u_pressure, uv - vec2(u_texel.x, 0.0)).x;\n' +
        '    float T = texture(u_pressure, uv + vec2(0.0, u_texel.y)).x;\n' +
        '    float B = texture(u_pressure, uv - vec2(0.0, u_texel.y)).x;\n' +
        '    float div = texture(u_divergence, uv).x;\n' +
        '    fragColor = vec4((L + R + B + T - div) * 0.25, 0.0, 0.0, 1.0);\n' +
        '}\n';

      var GRADIENT_FRAG = '#version 300 es\n' +
        'precision highp float;\n' +
        'uniform sampler2D u_vel;\n' +
        'uniform sampler2D u_pressure;\n' +
        'uniform vec2 u_texel;\n' +
        'out vec4 fragColor;\n' +
        'void main() {\n' +
        '    vec2 uv = gl_FragCoord.xy * u_texel;\n' +
        '    float R = texture(u_pressure, uv + vec2(u_texel.x, 0.0)).x;\n' +
        '    float L = texture(u_pressure, uv - vec2(u_texel.x, 0.0)).x;\n' +
        '    float T = texture(u_pressure, uv + vec2(0.0, u_texel.y)).x;\n' +
        '    float B = texture(u_pressure, uv - vec2(0.0, u_texel.y)).x;\n' +
        '    vec4 v = texture(u_vel, uv);\n' +
        '    v.xy -= 0.5 * vec2(R - L, T - B);\n' +
        '    // Boundary: reflect velocity at edges\n' +
        '    float edge = u_texel.x * 3.0;\n' +
        '    if (uv.x < edge) v.x = abs(v.x) * 0.95;\n' +
        '    if (uv.x > 1.0 - edge) v.x = -abs(v.x) * 0.95;\n' +
        '    if (uv.y < edge) v.y = abs(v.y) * 0.95;\n' +
        '    if (uv.y > 1.0 - edge) v.y = -abs(v.y) * 0.95;\n' +
        '    fragColor = v;\n' +
        '}\n';

      var RENDER_FRAG = '#version 300 es\n' +
        'precision highp float;\n' +
        'uniform sampler2D u_vel;\n' +
        'uniform sampler2D u_curl;\n' +
        'uniform vec2 u_texel;\n' +
        'uniform vec3 u_color1;\n' +
        'uniform vec3 u_color2;\n' +
        'uniform vec3 u_color3;\n' +
        'out vec4 fragColor;\n' +
        'void main() {\n' +
        '    vec2 uv = gl_FragCoord.xy * u_texel;\n' +
        '    vec2 vel = texture(u_vel, uv).xy;\n' +
        '    float curl = texture(u_curl, uv).x;\n' +
        '    float speed = length(vel);\n' +
        '    vec2 dir = speed > 0.001 ? vel / speed : vec2(0.0);\n' +
        '    vec2 perp = vec2(-dir.y, dir.x);\n' +
        '    // Radial offset from screen center\n' +
        '    vec2 fromCenter = uv - 0.5;\n' +
        '    float radial = length(fromCenter) * 0.008;\n' +
        '    vec2 radDir = normalize(fromCenter + 0.0001);\n' +
        '    // Velocity-based aberration\n' +
        '    float velAberr = speed * 0.03;\n' +
        '    // Curl-based perpendicular aberration\n' +
        '    float curlAberr = abs(curl) * 0.02;\n' +
        '    // Combined offsets per channel\n' +
        '    vec2 offR = dir * velAberr + perp * curlAberr + radDir * radial;\n' +
        '    vec2 offG = perp * curlAberr * 0.3;\n' +
        '    vec2 offB = -dir * velAberr - perp * curlAberr - radDir * radial;\n' +
        '    // Sample\n' +
        '    float r = length(texture(u_vel, uv + offR).xy);\n' +
        '    float g = length(texture(u_vel, uv + offG).xy);\n' +
        '    float b = length(texture(u_vel, uv + offB).xy);\n' +
        '    float s = smoothstep(0.01, 0.06, max(max(r, g), b));\n' +
        '    vec3 col = vec3(r, g, b) * s * 4.0;\n' +
        '    fragColor = vec4(col, 1.0);\n' +
        '}\n';

      // --- State ---
      var gl = null, vao = null;
      var prog = {};
      var velA, velB, divFbo, curlFbo, presA, presB;
      var simW = 0, simH = 0;
      var lastMX = -1, lastMY = -1, phase = 0;

      function makeShader(type, src) {
        var s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
          console.error('[gl-fluid]', gl.getShaderInfoLog(s));
          return null;
        }
        return s;
      }
      function link(frag) {
        var vs = makeShader(gl.VERTEX_SHADER, VERT);
        var fs = makeShader(gl.FRAGMENT_SHADER, frag);
        if (!vs || !fs) return null;
        var p = gl.createProgram();
        gl.attachShader(p, vs); gl.attachShader(p, fs);
        gl.linkProgram(p);
        if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
          console.error('[gl-fluid] link:', gl.getProgramInfoLog(p));
          return null;
        }
        gl.deleteShader(vs); gl.deleteShader(fs);
        return p;
      }
      function fbo(w, h) {
        var tex = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        var fb = gl.createFramebuffer();
        gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        return { fb: fb, tex: tex, w: w, h: h };
      }
      function blit(target) {
        gl.bindFramebuffer(gl.FRAMEBUFFER, target.fb);
        gl.viewport(0, 0, target.w, target.h);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      }
      function uni(p, name) { return gl.getUniformLocation(p, name); }

      function glFluidInit() {
        var c = ssGetGLCanvas();
        c.width = window.innerWidth;
        c.height = window.innerHeight;
        gl = c.getContext('webgl2', { alpha: false, antialias: false });
        if (!gl) return;
        gl.getExtension('EXT_color_buffer_float');
        vao = gl.createVertexArray();
        gl.bindVertexArray(vao);

        // Velocity at 3/4 screen res
        simW = Math.floor(c.width * 0.75);
        simH = Math.floor(c.height * 0.75);

        prog.advect = link(ADVECT_FRAG);
        prog.splat = link(SPLAT_FRAG);
        prog.curl = link(CURL_FRAG);
        prog.vorticity = link(VORTICITY_FRAG);
        prog.divergence = link(DIVERGENCE_FRAG);
        prog.pressure = link(PRESSURE_FRAG);
        prog.gradient = link(GRADIENT_FRAG);
        prog.render = link(RENDER_FRAG);

        if (!prog.advect || !prog.splat || !prog.curl || !prog.vorticity || !prog.divergence || !prog.pressure || !prog.gradient || !prog.render) {
          console.error('[gl-fluid] Shader compilation failed');
          gl = null; return;
        }

        velA = fbo(simW, simH);
        velB = fbo(simW, simH);
        divFbo = fbo(simW, simH);
        curlFbo = fbo(simW, simH);
        presA = fbo(simW, simH);
        presB = fbo(simW, simH);

        // Clear all
        gl.clearColor(0, 0, 0, 0);
        [velA, velB, divFbo, curlFbo, presA, presB].forEach(function(f) {
          gl.bindFramebuffer(gl.FRAMEBUFFER, f.fb);
          gl.clear(gl.COLOR_BUFFER_BIT);
        });
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        lastMX = -1; lastMY = -1; phase = 0;
      }

      function glFluidDraw() {
        if (!gl || !prog.advect) return;
        var cW = gl.drawingBufferWidth;
        var cH = gl.drawingBufferHeight;
        var simTx = [1.0/simW, 1.0/simH];

        // --- Mouse splat (interpolated multi-point for smooth strokes) ---
        var rawMX = ssMouseState.x;
        var rawMY = ssMouseState.y;
        if (rawMX >= 0 && rawMY >= 0 && lastMX >= 0 && lastMY >= 0) {
          var mx = rawMX / cW;
          var my = 1.0 - rawMY / cH;
          var pmx = lastMX / cW;
          var pmy = 1.0 - lastMY / cH;
          var dx = mx - pmx;
          var dy = my - pmy;
          var dist = Math.sqrt(dx * dx + dy * dy);
          if (dist > 0.00001) {
            // Interpolate: more sub-splats for faster movement
            var steps = Math.max(1, Math.floor(dist / 0.005));
            var sdx = dx / steps;
            var sdy = dy / steps;
            // Force proportional to speed
            var fx = dx * 120.0 / steps;
            var fy = dy * 120.0 / steps;
            // Jitter scales with speed — no jitter when slow
            var jitterScale = Math.min(dist * 20.0, 1.0);
            gl.useProgram(prog.splat);
            gl.uniform1i(uni(prog.splat, 'u_state'), 0);
            gl.uniform2f(uni(prog.splat, 'u_texel'), simTx[0], simTx[1]);
            gl.uniform1f(uni(prog.splat, 'u_radius'), 0.0025);
            for (var si = 0; si < steps; si++) {
              var px = pmx + sdx * (si + 0.5);
              var py = pmy + sdy * (si + 0.5);
              // Jitter only at speed
              var jx = (Math.random() - 0.5) * 0.004 * jitterScale;
              var jy = (Math.random() - 0.5) * 0.004 * jitterScale;
              var fJitter = 0.7 + Math.random() * 0.6;
              gl.uniform2f(uni(prog.splat, 'u_point'), px + jx, py + jy);
              gl.uniform3f(uni(prog.splat, 'u_value'), fx * fJitter, fy * fJitter, 0.0);
              gl.activeTexture(gl.TEXTURE0);
              gl.bindTexture(gl.TEXTURE_2D, velA.tex);
              blit(velB);
              var t = velA; velA = velB; velB = t;
            }
          }
        }
        lastMX = rawMX;
        lastMY = rawMY;

        // --- Advect velocity ---
        gl.useProgram(prog.advect);
        gl.uniform1i(uni(prog.advect, 'u_vel'), 0);
        gl.uniform1i(uni(prog.advect, 'u_source'), 0);
        gl.uniform2f(uni(prog.advect, 'u_texel'), simTx[0], simTx[1]);
        gl.uniform1f(uni(prog.advect, 'u_dt'), 0.04);
        gl.uniform1f(uni(prog.advect, 'u_dissipation'), 0.996);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, velA.tex);
        blit(velB);
        var tmp = velA; velA = velB; velB = tmp;

        // --- Divergence ---
        gl.useProgram(prog.divergence);
        gl.uniform1i(uni(prog.divergence, 'u_vel'), 0);
        gl.uniform2f(uni(prog.divergence, 'u_texel'), simTx[0], simTx[1]);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, velA.tex);
        blit(divFbo);

        // --- Pressure solve (30 Jacobi iterations) ---
        gl.useProgram(prog.pressure);
        gl.uniform1i(uni(prog.pressure, 'u_pressure'), 0);
        gl.uniform1i(uni(prog.pressure, 'u_divergence'), 1);
        gl.uniform2f(uni(prog.pressure, 'u_texel'), simTx[0], simTx[1]);
        gl.activeTexture(gl.TEXTURE1);
        gl.bindTexture(gl.TEXTURE_2D, divFbo.tex);
        // Clear pressure before solve
        gl.bindFramebuffer(gl.FRAMEBUFFER, presA.fb);
        gl.viewport(0, 0, simW, simH);
        gl.clearColor(0,0,0,1);
        gl.clear(gl.COLOR_BUFFER_BIT);
        for (var i = 0; i < 40; i++) {
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, presA.tex);
          blit(presB);
          tmp = presA; presA = presB; presB = tmp;
        }

        // --- Gradient subtraction ---
        gl.useProgram(prog.gradient);
        gl.uniform1i(uni(prog.gradient, 'u_vel'), 0);
        gl.uniform1i(uni(prog.gradient, 'u_pressure'), 1);
        gl.uniform2f(uni(prog.gradient, 'u_texel'), simTx[0], simTx[1]);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, velA.tex);
        gl.activeTexture(gl.TEXTURE1);
        gl.bindTexture(gl.TEXTURE_2D, presA.tex);
        blit(velB);
        tmp = velA; velA = velB; velB = tmp;

        // --- Compute curl for visualization ---
        gl.useProgram(prog.curl);
        gl.uniform1i(uni(prog.curl, 'u_vel'), 0);
        gl.uniform2f(uni(prog.curl, 'u_texel'), simTx[0], simTx[1]);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, velA.tex);
        blit(curlFbo);

        // --- Render to screen ---
        var style = getComputedStyle(document.documentElement);
        function h(hex) {
          hex = (hex || '#ffffff').replace('#','');
          return [parseInt(hex.slice(0,2),16)/255, parseInt(hex.slice(2,4),16)/255, parseInt(hex.slice(4,6),16)/255];
        }
        var v1 = h(style.getPropertyValue('--accent').trim());
        var v2 = h(style.getPropertyValue('--warm').trim());
        var v3 = h(style.getPropertyValue('--cool').trim());

        gl.useProgram(prog.render);
        gl.uniform1i(uni(prog.render, 'u_vel'), 0);
        gl.uniform1i(uni(prog.render, 'u_curl'), 1);
        gl.uniform2f(uni(prog.render, 'u_texel'), 1.0/cW, 1.0/cH);
        gl.uniform3f(uni(prog.render, 'u_color1'), v1[0], v1[1], v1[2]);
        gl.uniform3f(uni(prog.render, 'u_color2'), v2[0], v2[1], v2[2]);
        gl.uniform3f(uni(prog.render, 'u_color3'), v3[0], v3[1], v3[2]);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, velA.tex);
        gl.activeTexture(gl.TEXTURE1);
        gl.bindTexture(gl.TEXTURE_2D, curlFbo.tex);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        gl.viewport(0, 0, cW, cH);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      }

      function glFluidResize() { glFluidCleanup(); glFluidInit(); }

      function glFluidCleanup() {
        if (!gl) return;
        [velA, velB, divFbo, curlFbo, presA, presB].forEach(function(f) {
          if (f) { gl.deleteFramebuffer(f.fb); gl.deleteTexture(f.tex); }
        });
        Object.keys(prog).forEach(function(k) { if (prog[k]) gl.deleteProgram(prog[k]); });
        prog = {};
        velA = velB = divFbo = curlFbo = presA = presB = null;
        gl = null;
      }

      function glFluidPreview(ctx, w, h) {
        var accent = ssGetAccent();
        var rgb = ssHexToRgb(accent);
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, w, h);
        ctx.strokeStyle = ssHexToRgba(accent, 0.5);
        ctx.lineWidth = 1.5;
        for (var i = 0; i < 8; i++) {
          ctx.beginPath();
          var sx = w * (0.2 + Math.sin(i * 0.8) * 0.3);
          var sy = h * (0.3 + Math.cos(i * 0.6) * 0.25);
          ctx.moveTo(sx, sy);
          for (var t = 0; t < 25; t++) {
            sx += Math.cos(t * 0.25 + i) * 4;
            sy += Math.sin(t * 0.35 + i * 0.5) * 3;
            ctx.lineTo(sx, sy);
          }
          ctx.stroke();
        }
      }

      ssModes['gl-chroma'] = {
        init: glFluidInit,
        draw: glFluidDraw,
        resize: glFluidResize,
        cleanup: glFluidCleanup,
        preview: glFluidPreview,
        gl: true
      };
    })();
