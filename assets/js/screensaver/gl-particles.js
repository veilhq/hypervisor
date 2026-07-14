/* === Screensaver Mode: GL Particles (GPU Fluid) === */

    // Dense GPU particle fluid — same visual as the CPU SPH particles mode
    // but running 10-20x more particles via transform feedback.
    // Uses simplified repulsion (no true neighbor search on GPU) but achieves
    // the fluid look through high particle count + viscous damping + mouse interaction.

    (function () {
      var PARTICLE_COUNT = 50000;
      var FLOATS_PER_PARTICLE = 4; // pos.x, pos.y, vel.x, vel.y

      // --- Update vertex shader ---
      var UPDATE_VERT = [
        '#version 300 es',
        'precision highp float;',
        '',
        'in vec2 a_position;',
        'in vec2 a_velocity;',
        '',
        'out vec2 v_position;',
        'out vec2 v_velocity;',
        '',
        'uniform vec2 u_resolution;',
        'uniform vec2 u_mouse;        // pixel coords, (-1,-1) = inactive',
        'uniform vec2 u_prevMouse;    // previous frame mouse pixel coords',
        'uniform float u_mouseRadius;',
        'uniform float u_dt;',
        'uniform float u_gravity;',
        '',
        'void main() {',
        '    vec2 pos = a_position;',
        '    vec2 vel = a_velocity;',
        '',
        '    // Gravity',
        '    vel.y += u_gravity * u_dt;',
        '',
        '    // Mouse interaction (in pixel space)',
        '    if (u_mouse.x >= 0.0) {',
        '        vec2 diff = pos - u_mouse;',
        '        float dist = length(diff);',
        '        if (dist < u_mouseRadius && dist > 1.0) {',
        '            float influence = 1.0 - (dist / u_mouseRadius);',
        '            influence = influence * influence;',
        '',
        '            // Radial repulsion',
        '            vec2 dir = diff / dist;',
        '            vel += dir * influence * 1400.0 * u_dt;',
        '',
        '            // Mouse drag force',
        '            vec2 mouseVel = u_mouse - u_prevMouse;',
        '            float mouseSpeed = length(mouseVel);',
        '            if (mouseSpeed > 1.0) {',
        '                vel += normalize(mouseVel) * influence * mouseSpeed * 0.7 * u_dt * 60.0;',
        '            }',
        '        }',
        '    }',
        '',
        '    // Damping (viscosity)',
        '    vel *= 0.997;',
        '',
        '    // Speed cap',
        '    float speed = length(vel);',
        '    if (speed > 700.0) {',
        '        vel = vel / speed * 700.0;',
        '    }',
        '',
        '    // Integrate',
        '    pos += vel * u_dt;',
        '',
        '    // Boundary collisions (bounce off walls)',
        '    float boundary = 5.0;',
        '    if (pos.x < boundary) { pos.x = boundary; vel.x *= -0.5; }',
        '    if (pos.x > u_resolution.x - boundary) { pos.x = u_resolution.x - boundary; vel.x *= -0.5; }',
        '    if (pos.y < boundary) { pos.y = boundary; vel.y *= -0.5; }',
        '    if (pos.y > u_resolution.y - boundary) { pos.y = u_resolution.y - boundary; vel.y *= -0.5; }',
        '',
        '    v_position = pos;',
        '    v_velocity = vel;',
        '}'
      ].join('\n');

      var UPDATE_FRAG = [
        '#version 300 es',
        'precision highp float;',
        'out vec4 fragColor;',
        'void main() { fragColor = vec4(0.0); }'
      ].join('\n');

      // --- Render vertex shader ---
      var RENDER_VERT = [
        '#version 300 es',
        'precision highp float;',
        '',
        'in vec2 a_position;',
        'in vec2 a_velocity;',
        '',
        'uniform vec2 u_resolution;',
        '',
        'out float vSpeed;',
        'out vec2 vVel;',
        '',
        'void main() {',
        '    // Convert pixel coords to clip space',
        '    vec2 clipPos = (a_position / u_resolution) * 2.0 - 1.0;',
        '    clipPos.y = -clipPos.y;  // flip Y (pixel space is top-down)',
        '    gl_Position = vec4(clipPos, 0.0, 1.0);',
        '',
        '    float speed = length(a_velocity);',
        '    vSpeed = speed;',
        '    vVel = a_velocity;',
        '',
        '    // Point size: bigger when fast (motion blur effect)',
        '    gl_PointSize = mix(2.0, 3.5, clamp(speed / 400.0, 0.0, 1.0));',
        '}'
      ].join('\n');

      // --- Render fragment shader ---
      var RENDER_FRAG = [
        '#version 300 es',
        'precision highp float;',
        '',
        'uniform vec3 u_accent;',
        'uniform vec3 u_palette[4];',
        'uniform int u_usePalette;',
        '',
        'in float vSpeed;',
        'in vec2 vVel;',
        '',
        'out vec4 fragColor;',
        '',
        'void main() {',
        '    float speedNorm = clamp(vSpeed / 500.0, 0.0, 1.0);',
        '    float alpha = 0.35 + speedNorm * 0.6;',
        '',
        '    vec3 col;',
        '    if (u_usePalette == 1) {',
        '        // Interpolate through palette based on speed',
        '        float idx = speedNorm * 3.0;',
        '        int ci = int(min(floor(idx), 2.0));',
        '        float frac = fract(idx);',
        '        vec3 cA = (ci == 0) ? u_palette[0] : (ci == 1) ? u_palette[1] : u_palette[2];',
        '        vec3 cB = (ci == 0) ? u_palette[1] : (ci == 1) ? u_palette[2] : u_palette[3];',
        '        col = mix(cA, cB, frac);',
        '    } else {',
        '        col = u_accent;',
        '    }',
        '',
        '    fragColor = vec4(col, alpha);',
        '}'
      ].join('\n');

      // --- Fade shader (draws semi-transparent black quad for trails) ---
      var FADE_VERT = [
        '#version 300 es',
        'void main() {',
        '    float x = float(gl_VertexID % 2) * 4.0 - 1.0;',
        '    float y = float(gl_VertexID / 2) * 4.0 - 1.0;',
        '    gl_Position = vec4(x, y, 0.0, 1.0);',
        '}'
      ].join('\n');

      var FADE_FRAG = [
        '#version 300 es',
        'precision highp float;',
        'uniform float u_fadeAlpha;',
        'out vec4 fragColor;',
        'void main() {',
        '    fragColor = vec4(0.0, 0.0, 0.0, u_fadeAlpha);',
        '}'
      ].join('\n');

      // --- State ---
      var gl = null;
      var glCanvas = null;
      var updateProgram = null;
      var renderProgram = null;
      var fadeProgram = null;
      var fadeLoc = null;
      var buffers = [null, null];
      var vaos = [null, null];
      var tf = null;
      var readIdx = 0;
      var writeIdx = 1;
      var lastTime = 0;
      var updateUniforms = {};
      var renderUniforms = {};
      var initialized = false;
      var prevMouseX = -1;
      var prevMouseY = -1;

      var STRIDE = FLOATS_PER_PARTICLE * 4; // 16 bytes

      function compileShader(type, source) {
        var shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
          console.error('[gl-particles] Shader error:', gl.getShaderInfoLog(shader));
          gl.deleteShader(shader);
          return null;
        }
        return shader;
      }

      function linkProgram(vertSrc, fragSrc, varyings) {
        var vert = compileShader(gl.VERTEX_SHADER, vertSrc);
        var frag = compileShader(gl.FRAGMENT_SHADER, fragSrc);
        if (!vert || !frag) return null;

        var prog = gl.createProgram();
        gl.attachShader(prog, vert);
        gl.attachShader(prog, frag);

        if (varyings) {
          gl.transformFeedbackVaryings(prog, varyings, gl.INTERLEAVED_ATTRIBS);
        }

        gl.linkProgram(prog);
        if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
          console.error('[gl-particles] Link error:', gl.getProgramInfoLog(prog));
          gl.deleteProgram(prog);
          return null;
        }

        gl.detachShader(prog, vert);
        gl.detachShader(prog, frag);
        gl.deleteShader(vert);
        gl.deleteShader(frag);
        return prog;
      }

      function getUniforms(prog) {
        var locs = {};
        var count = gl.getProgramParameter(prog, gl.ACTIVE_UNIFORMS);
        for (var i = 0; i < count; i++) {
          var info = gl.getActiveUniform(prog, i);
          if (info) {
            var name = info.name.replace(/\[0\]$/, '');
            locs[name] = gl.getUniformLocation(prog, info.name);
          }
        }
        return locs;
      }

      function setupVAO(vao, buffer) {
        gl.bindVertexArray(vao);
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);

        // a_position: vec2 at offset 0
        gl.enableVertexAttribArray(0);
        gl.vertexAttribPointer(0, 2, gl.FLOAT, false, STRIDE, 0);

        // a_velocity: vec2 at offset 8
        gl.enableVertexAttribArray(1);
        gl.vertexAttribPointer(1, 2, gl.FLOAT, false, STRIDE, 8);

        gl.bindVertexArray(null);
        gl.bindBuffer(gl.ARRAY_BUFFER, null);
      }

      function initParticleData() {
        var w = glCanvas.width;
        var h = glCanvas.height;
        var data = new Float32Array(PARTICLE_COUNT * FLOATS_PER_PARTICLE);
        // Distribute in a grid-like pattern with jitter (mimics CPU version)
        var aspect = w / h;
        var rowCount = Math.round(Math.sqrt(PARTICLE_COUNT / aspect));
        var colCount = Math.round(PARTICLE_COUNT / rowCount);
        var spacingX = w / (colCount + 1);
        var spacingY = h / (rowCount + 1);

        for (var i = 0; i < PARTICLE_COUNT; i++) {
          var base = i * FLOATS_PER_PARTICLE;
          var row = Math.floor(i / colCount);
          var col = i % colCount;
          var px = (col + 1) * spacingX + (Math.random() - 0.5) * spacingX * 0.5;
          var py = (row + 1) * spacingY + (Math.random() - 0.5) * spacingY * 0.5;

          // Clamp to bounds
          px = Math.max(5, Math.min(w - 5, px));
          py = Math.max(5, Math.min(h - 5, py));

          data[base + 0] = px;
          data[base + 1] = py;
          data[base + 2] = 0.0; // vx
          data[base + 3] = 0.0; // vy
        }
        return data;
      }

      function init() {
        glCanvas = ssGetGLCanvas();
        glCanvas.width = window.innerWidth;
        glCanvas.height = window.innerHeight;

        if (!gl || gl.isContextLost()) {
          gl = glCanvas.getContext('webgl2', { alpha: true, antialias: false, preserveDrawingBuffer: false });
          if (!gl) {
            console.error('[gl-particles] WebGL2 not available');
            return;
          }
          initialized = false;
        }

        if (!initialized) {
          updateProgram = linkProgram(UPDATE_VERT, UPDATE_FRAG, ['v_position', 'v_velocity']);
          renderProgram = linkProgram(RENDER_VERT, RENDER_FRAG, null);
          fadeProgram = linkProgram(FADE_VERT, FADE_FRAG, null);

          if (!updateProgram || !renderProgram || !fadeProgram) {
            console.error('[gl-particles] Failed to compile shaders');
            return;
          }

          updateUniforms = getUniforms(updateProgram);
          renderUniforms = getUniforms(renderProgram);
          fadeLoc = gl.getUniformLocation(fadeProgram, 'u_fadeAlpha');

          // Create double buffers
          var particleData = initParticleData();
          for (var i = 0; i < 2; i++) {
            buffers[i] = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, buffers[i]);
            gl.bufferData(gl.ARRAY_BUFFER, particleData, gl.DYNAMIC_DRAW);
          }
          gl.bindBuffer(gl.ARRAY_BUFFER, null);

          // Create VAOs
          vaos[0] = gl.createVertexArray();
          vaos[1] = gl.createVertexArray();
          setupVAO(vaos[0], buffers[0]);
          setupVAO(vaos[1], buffers[1]);

          // Create transform feedback object
          tf = gl.createTransformFeedback();

          initialized = true;
        }

        readIdx = 0;
        writeIdx = 1;
        lastTime = performance.now() / 1000;
        prevMouseX = -1;
        prevMouseY = -1;

        gl.viewport(0, 0, glCanvas.width, glCanvas.height);
        gl.clearColor(0.0, 0.0, 0.0, 1.0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
      }

      function draw() {
        if (!gl || !initialized) return;

        var now = performance.now() / 1000;
        var dt = Math.min(now - lastTime, 0.033); // cap at ~30fps minimum step
        lastTime = now;

        var w = glCanvas.width;
        var h = glCanvas.height;

        // Mouse in pixel coords (matching the CPU version's behavior)
        var mx = ssMouseState.x;
        var my = ssMouseState.y;

        // === FADE PASS (trail effect) ===
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.useProgram(fadeProgram);
        gl.uniform1f(fadeLoc, 0.06);
        gl.drawArrays(gl.TRIANGLES, 0, 3);

        // === UPDATE PASS ===
        gl.useProgram(updateProgram);
        gl.uniform2f(updateUniforms.u_resolution, w, h);
        gl.uniform2f(updateUniforms.u_mouse, mx, my);
        gl.uniform2f(updateUniforms.u_prevMouse, prevMouseX >= 0 ? prevMouseX : mx, prevMouseY >= 0 ? prevMouseY : my);
        gl.uniform1f(updateUniforms.u_mouseRadius, 180.0);
        gl.uniform1f(updateUniforms.u_dt, dt);
        gl.uniform1f(updateUniforms.u_gravity, 0.0);

        gl.bindVertexArray(vaos[readIdx]);
        gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, tf);
        gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, buffers[writeIdx]);

        gl.enable(gl.RASTERIZER_DISCARD);
        gl.beginTransformFeedback(gl.POINTS);
        gl.drawArrays(gl.POINTS, 0, PARTICLE_COUNT);
        gl.endTransformFeedback();
        gl.disable(gl.RASTERIZER_DISCARD);

        gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, null);
        gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, null);
        gl.bindVertexArray(null);

        // === RENDER PASS (additive blending for glow) ===
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
        gl.useProgram(renderProgram);
        gl.uniform2f(renderUniforms.u_resolution, w, h);

        // Accent color
        var accentHex = ssGetAccent();
        var rgb = ssHexToRgb(accentHex);
        gl.uniform3f(renderUniforms.u_accent, rgb.r / 255, rgb.g / 255, rgb.b / 255);

        // Palette
        var usePal = ssUsePalette() ? 1 : 0;
        gl.uniform1i(renderUniforms.u_usePalette, usePal);
        if (usePal) {
          var palette = ssGetPalette();
          var flat = [];
          for (var i = 0; i < 4; i++) {
            var c = ssHexToRgb(palette[i]);
            flat.push(c.r / 255, c.g / 255, c.b / 255);
          }
          gl.uniform3fv(renderUniforms['u_palette'], flat);
        }

        gl.bindVertexArray(vaos[writeIdx]);
        gl.drawArrays(gl.POINTS, 0, PARTICLE_COUNT);
        gl.bindVertexArray(null);

        // Swap
        var tmp = readIdx;
        readIdx = writeIdx;
        writeIdx = tmp;

        // Store previous mouse
        prevMouseX = mx;
        prevMouseY = my;
      }

      function resize() {
        if (!glCanvas) return;
        glCanvas.width = window.innerWidth;
        glCanvas.height = window.innerHeight;
        if (gl) gl.viewport(0, 0, glCanvas.width, glCanvas.height);
      }

      function cleanup() {
        // Keep GL resources for re-activation
      }

      function preview(ctx, w, h) {
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, w, h);
        var accent = ssGetAccent();
        var rgb = ssHexToRgb(accent);
        // Mimic dense particle field
        for (var i = 0; i < 600; i++) {
          var px = Math.random() * w;
          var py = Math.random() * h;
          var alpha = 0.3 + Math.random() * 0.4;
          ctx.fillStyle = 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + alpha + ')';
          ctx.beginPath();
          ctx.arc(px, py, 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      ssModes['gl-particles'] = {
        init: init,
        draw: draw,
        resize: resize,
        cleanup: cleanup,
        preview: preview,
        gl: true
      };
    })();
