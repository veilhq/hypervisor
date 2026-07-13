/* === HyperGL — WebGL2 Integration Layer === */

    // A thin, zero-dependency WebGL2 runtime layer for the hyper ecosystem.
    // Any consumer (screensaver modes, page backgrounds, effects) can use
    // HyperGL.create() to spin up GPU-accelerated shader effects.

    var HyperGL = (function () {

      // --- Default fullscreen triangle vertex shader ---
      // Covers the entire viewport with 3 vertices, no buffer needed.
      var FULLSCREEN_VERT = [
        '#version 300 es',
        'out vec2 vUv;',
        'void main() {',
        '    float x = float(gl_VertexID % 2) * 4.0 - 1.0;',
        '    float y = float(gl_VertexID / 2) * 4.0 - 1.0;',
        '    vUv = vec2(x, y) * 0.5 + 0.5;',
        '    gl_Position = vec4(x, y, 0.0, 1.0);',
        '}'
      ].join('\n');

      // --- Shader compilation ---
      function compileShader(gl, type, source) {
        var shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
          var typeStr = type === gl.VERTEX_SHADER ? 'VERTEX' : 'FRAGMENT';
          console.error('[HyperGL] ' + typeStr + ' shader compilation failed:\n' +
            gl.getShaderInfoLog(shader));
          gl.deleteShader(shader);
          return null;
        }
        return shader;
      }

      // --- Program linking ---
      function createProgram(gl, vertSrc, fragSrc, feedbackVaryings) {
        var vert = compileShader(gl, gl.VERTEX_SHADER, vertSrc);
        var frag = compileShader(gl, gl.FRAGMENT_SHADER, fragSrc);
        if (!vert || !frag) return null;

        var program = gl.createProgram();
        gl.attachShader(program, vert);
        gl.attachShader(program, frag);

        if (feedbackVaryings && feedbackVaryings.length > 0) {
          gl.transformFeedbackVaryings(program, feedbackVaryings, gl.INTERLEAVED_ATTRIBS);
        }

        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
          console.error('[HyperGL] Program link failed:\n' + gl.getProgramInfoLog(program));
          gl.deleteProgram(program);
          return null;
        }

        // Detach and delete shaders after linking (they're baked into the program)
        gl.detachShader(program, vert);
        gl.detachShader(program, frag);
        gl.deleteShader(vert);
        gl.deleteShader(frag);

        return program;
      }

      // --- Uniform location cache ---
      function getUniformLocations(gl, program) {
        var locs = {};
        var count = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);
        for (var i = 0; i < count; i++) {
          var info = gl.getActiveUniform(program, i);
          if (info) {
            // Strip array suffix for uniform arrays
            var name = info.name.replace(/\[0\]$/, '');
            locs[name] = gl.getUniformLocation(program, info.name);
          }
        }
        return locs;
      }

      // --- Parse hex color to normalized RGB ---
      function hexToVec3(hex) {
        hex = hex.replace('#', '');
        return [
          parseInt(hex.slice(0, 2), 16) / 255,
          parseInt(hex.slice(2, 4), 16) / 255,
          parseInt(hex.slice(4, 6), 16) / 255
        ];
      }

      // --- Read accent and palette from CSS ---
      function readAccent() {
        var style = getComputedStyle(document.documentElement);
        return style.getPropertyValue('--accent').trim() || '#00ff41';
      }

      function readPalette() {
        var style = getComputedStyle(document.documentElement);
        return [
          style.getPropertyValue('--accent').trim() || '#00ff41',
          style.getPropertyValue('--warm').trim() || '#ff6600',
          style.getPropertyValue('--cool').trim() || '#00cccc',
          style.getPropertyValue('--comp').trim() || '#cc00cc'
        ];
      }

      // --- Public factory ---
      function create(opts) {
        if (!opts || !opts.target) {
          console.error('[HyperGL] opts.target is required');
          return null;
        }

        // Create canvas
        var canvas;
        if (opts.target.tagName === 'CANVAS') {
          canvas = opts.target;
        } else {
          canvas = document.createElement('canvas');
          canvas.style.position = 'absolute';
          canvas.style.top = '0';
          canvas.style.left = '0';
          canvas.style.width = '100%';
          canvas.style.height = '100%';
          opts.target.appendChild(canvas);
        }

        // Acquire WebGL2 context
        var glOpts = { alpha: !!opts.alpha, antialias: false, preserveDrawingBuffer: false };
        var gl = canvas.getContext('webgl2', glOpts);
        if (!gl) {
          console.error('[HyperGL] WebGL2 not available');
          if (canvas.parentNode && canvas !== opts.target) {
            canvas.parentNode.removeChild(canvas);
          }
          return null;
        }

        // Enable float FBO extension (needed for ping-pong with float textures)
        gl.getExtension('EXT_color_buffer_float');

        // State
        var pixelRatio = opts.pixelRatio || 1;
        var programs = {};      // key -> { program, uniforms }
        var activeKey = null;   // current active program key
        var startTime = performance.now();
        var frameCount = 0;
        var animFrame = null;
        var running = false;
        var mouseX = -1, mouseY = -1;
        var destroyed = false;

        // Ping-pong state
        var pingPong = null;    // { fbos: [fbo0, fbo1], textures: [tex0, tex1], read: 0, write: 1, width, height }

        // Transform feedback state
        var tfState = null;     // { buffers: [buf0, buf1], vaos: [vao0, vao1], read: 0, write: 1, tf }

        // Custom uniforms
        var customUniforms = opts.uniforms ? Object.assign({}, opts.uniforms) : {};

        // --- Compile primary program ---
        var vertSrc = opts.vertex || FULLSCREEN_VERT;
        var fragSrc = opts.fragment || '';
        var feedbackVaryings = opts.feedbackVaryings || null;

        if (fragSrc) {
          var prog = createProgram(gl, vertSrc, fragSrc, feedbackVaryings);
          if (prog) {
            programs['_primary'] = { program: prog, uniforms: getUniformLocations(gl, prog) };
            activeKey = '_primary';
            gl.useProgram(prog);
          } else {
            // Inert instance — shader failed to compile
            console.warn('[HyperGL] Primary shader failed. Instance is inert.');
          }
        }

        // --- Sizing ---
        function resize() {
          if (destroyed) return;
          var rect = canvas.parentNode ? canvas.parentNode.getBoundingClientRect() :
                     { width: canvas.clientWidth, height: canvas.clientHeight };
          var w = Math.floor((rect.width || canvas.width) * pixelRatio);
          var h = Math.floor((rect.height || canvas.height) * pixelRatio);
          // Don't resize to 0 — parent might be hidden
          if (w <= 0 || h <= 0) return;
          if (canvas.width !== w || canvas.height !== h) {
            canvas.width = w;
            canvas.height = h;
          }
          gl.viewport(0, 0, canvas.width, canvas.height);
        }
        resize();

        // --- Mouse tracking ---
        function onMouseMove(e) {
          var rect = canvas.getBoundingClientRect();
          mouseX = (e.clientX - rect.left) / rect.width;
          mouseY = 1.0 - (e.clientY - rect.top) / rect.height;
        }
        function onMouseLeave() {
          mouseX = -1;
          mouseY = -1;
        }
        canvas.addEventListener('mousemove', onMouseMove);
        canvas.addEventListener('mouseleave', onMouseLeave);

        // --- Context loss handling ---
        function onContextLost(e) {
          e.preventDefault();
          running = false;
          if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
          console.warn('[HyperGL] WebGL context lost');
        }
        function onContextRestored() {
          console.info('[HyperGL] WebGL context restored');
          // Re-compilation would be needed here for full recovery
        }
        canvas.addEventListener('webglcontextlost', onContextLost);
        canvas.addEventListener('webglcontextrestored', onContextRestored);

        // --- Bind standard uniforms ---
        function bindStandardUniforms(time) {
          var p = programs[activeKey];
          if (!p) return;
          var u = p.uniforms;

          if (u.u_time != null) gl.uniform1f(u.u_time, time);
          if (u.u_resolution != null) gl.uniform2f(u.u_resolution, canvas.width, canvas.height);
          if (u.u_mouse != null) gl.uniform2f(u.u_mouse, mouseX, mouseY);
          if (u.u_frame != null) gl.uniform1i(u.u_frame, frameCount);

          if (u.u_accent != null) {
            var a = hexToVec3(readAccent());
            gl.uniform3f(u.u_accent, a[0], a[1], a[2]);
          }
          if (u.u_palette != null) {
            var pal = readPalette();
            var flat = [];
            for (var i = 0; i < 4; i++) {
              var c = hexToVec3(pal[i]);
              flat.push(c[0], c[1], c[2]);
            }
            gl.uniform3fv(u.u_palette, flat);
          }

          // Bind custom uniforms
          for (var key in customUniforms) {
            if (u[key] != null) {
              setUniformValue(gl, u[key], customUniforms[key]);
            }
          }
        }

        // --- Set a uniform value (type-inferred) ---
        function setUniformValue(glCtx, loc, val) {
          if (loc == null) return;
          if (typeof val === 'number') {
            if (Number.isInteger(val) && Math.abs(val) < 2147483647) {
              // Heuristic: treat as float since most shader uniforms are float
              glCtx.uniform1f(loc, val);
            } else {
              glCtx.uniform1f(loc, val);
            }
          } else if (Array.isArray(val) || (val && val.length !== undefined)) {
            switch (val.length) {
              case 2: glCtx.uniform2fv(loc, val); break;
              case 3: glCtx.uniform3fv(loc, val); break;
              case 4: glCtx.uniform4fv(loc, val); break;
              case 9: glCtx.uniformMatrix3fv(loc, false, val); break;
              case 16: glCtx.uniformMatrix4fv(loc, false, val); break;
              default: glCtx.uniform1fv(loc, val); break;
            }
          }
        }

        // --- Render one frame ---
        function render(time) {
          if (destroyed || !programs[activeKey]) return;
          if (time === undefined) time = (performance.now() - startTime) / 1000;

          gl.viewport(0, 0, canvas.width, canvas.height);
          var p = programs[activeKey];
          gl.useProgram(p.program);
          bindStandardUniforms(time);
          gl.drawArrays(gl.TRIANGLES, 0, 3);
          frameCount++;
        }

        // --- Frame loop ---
        function loop(timestamp) {
          if (!running || destroyed) return;
          var time = (timestamp - startTime) / 1000;
          render(time);
          animFrame = requestAnimationFrame(loop);
        }

        function start() {
          if (running || destroyed) return;
          running = true;
          startTime = performance.now();
          frameCount = 0;
          animFrame = requestAnimationFrame(loop);
        }

        function stop() {
          running = false;
          if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
        }

        // --- Multi-program support ---
        function addProgram(key, fragSrc, vertSrc) {
          if (destroyed) return;
          var vs = vertSrc || FULLSCREEN_VERT;
          var prog = createProgram(gl, vs, fragSrc, null);
          if (prog) {
            programs[key] = { program: prog, uniforms: getUniformLocations(gl, prog) };
          } else {
            console.error('[HyperGL] Failed to compile program: ' + key);
          }
        }

        function useProgram(key) {
          if (destroyed) return;
          if (key === null || key === undefined) key = '_primary';
          if (programs[key]) {
            activeKey = key;
            gl.useProgram(programs[key].program);
          }
        }

        // --- Ping-pong FBO ---
        function createPingPongFBO(w, h) {
          if (destroyed) return;
          // Clean up existing
          if (pingPong) destroyPingPong();

          var fbos = [];
          var textures = [];
          for (var i = 0; i < 2; i++) {
            var tex = gl.createTexture();
            gl.bindTexture(gl.TEXTURE_2D, tex);
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, w, h, 0, gl.RGBA, gl.FLOAT, null);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

            var fbo = gl.createFramebuffer();
            gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
            gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);

            var status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
            if (status !== gl.FRAMEBUFFER_COMPLETE) {
              console.error('[HyperGL] FBO incomplete (status: ' + status + '). Trying RGBA16F fallback.');
              // Fallback to half-float
              gl.bindTexture(gl.TEXTURE_2D, tex);
              gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null);
              gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
            }

            fbos.push(fbo);
            textures.push(tex);
          }
          gl.bindFramebuffer(gl.FRAMEBUFFER, null);
          gl.bindTexture(gl.TEXTURE_2D, null);

          pingPong = { fbos: fbos, textures: textures, read: 0, write: 1, width: w, height: h };
        }

        function swap() {
          if (!pingPong) return;
          var tmp = pingPong.read;
          pingPong.read = pingPong.write;
          pingPong.write = tmp;
        }

        function destroyPingPong() {
          if (!pingPong) return;
          for (var i = 0; i < 2; i++) {
            gl.deleteFramebuffer(pingPong.fbos[i]);
            gl.deleteTexture(pingPong.textures[i]);
          }
          pingPong = null;
        }

        // --- Transform feedback ---
        function createTransformFeedback(bufferSize) {
          if (destroyed) return;
          var buffers = [gl.createBuffer(), gl.createBuffer()];
          var vaos = [gl.createVertexArray(), gl.createVertexArray()];
          var tf = gl.createTransformFeedback();

          for (var i = 0; i < 2; i++) {
            gl.bindBuffer(gl.ARRAY_BUFFER, buffers[i]);
            gl.bufferData(gl.ARRAY_BUFFER, bufferSize, gl.DYNAMIC_DRAW);
          }
          gl.bindBuffer(gl.ARRAY_BUFFER, null);

          tfState = { buffers: buffers, vaos: vaos, read: 0, write: 1, tf: tf };
        }

        function swapTransformFeedback() {
          if (!tfState) return;
          var tmp = tfState.read;
          tfState.read = tfState.write;
          tfState.write = tmp;
        }

        function destroyTransformFeedback() {
          if (!tfState) return;
          gl.deleteBuffer(tfState.buffers[0]);
          gl.deleteBuffer(tfState.buffers[1]);
          gl.deleteVertexArray(tfState.vaos[0]);
          gl.deleteVertexArray(tfState.vaos[1]);
          gl.deleteTransformFeedback(tfState.tf);
          tfState = null;
        }

        // --- Destroy ---
        function destroy() {
          if (destroyed) return;
          destroyed = true;
          stop();

          // Remove listeners
          canvas.removeEventListener('mousemove', onMouseMove);
          canvas.removeEventListener('mouseleave', onMouseLeave);
          canvas.removeEventListener('webglcontextlost', onContextLost);
          canvas.removeEventListener('webglcontextrestored', onContextRestored);

          // Clean up GL resources
          destroyPingPong();
          destroyTransformFeedback();
          for (var key in programs) {
            gl.deleteProgram(programs[key].program);
          }
          programs = {};

          // Lose context
          var loseCtx = gl.getExtension('WEBGL_lose_context');
          if (loseCtx) loseCtx.loseContext();

          // Remove canvas if we created it
          if (canvas !== opts.target && canvas.parentNode) {
            canvas.parentNode.removeChild(canvas);
          }
        }

        // --- Auto-start if loop mode ---
        if (opts.loop && programs[activeKey]) {
          start();
        }

        // --- Public instance ---
        return {
          gl: gl,
          canvas: canvas,
          start: start,
          stop: stop,
          render: render,
          resize: resize,
          destroy: destroy,
          setUniform: function (name, value) {
            customUniforms[name] = value;
            // Immediately apply if a program is active
            var p = programs[activeKey];
            if (p && p.uniforms[name] != null) {
              gl.useProgram(p.program);
              setUniformValue(gl, p.uniforms[name], value);
            }
          },
          addProgram: addProgram,
          useProgram: useProgram,
          createPingPong: createPingPongFBO,
          swap: swap,
          getPingPong: function () { return pingPong; },
          createTransformFeedback: createTransformFeedback,
          swapTransformFeedback: swapTransformFeedback,
          getTransformFeedback: function () { return tfState; },
          bindFBO: function (which) {
            // which: 'read', 'write', or null (screen)
            if (!pingPong) return;
            if (which === 'write') {
              gl.bindFramebuffer(gl.FRAMEBUFFER, pingPong.fbos[pingPong.write]);
              gl.viewport(0, 0, pingPong.width, pingPong.height);
            } else if (which === 'read') {
              gl.bindFramebuffer(gl.FRAMEBUFFER, pingPong.fbos[pingPong.read]);
              gl.viewport(0, 0, pingPong.width, pingPong.height);
            } else {
              gl.bindFramebuffer(gl.FRAMEBUFFER, null);
              gl.viewport(0, 0, canvas.width, canvas.height);
            }
          },
          bindTexture: function (unit, which) {
            // Bind a ping-pong texture to a texture unit
            if (!pingPong) return;
            var tex = which === 'write' ? pingPong.textures[pingPong.write] :
                                          pingPong.textures[pingPong.read];
            gl.activeTexture(gl.TEXTURE0 + (unit || 0));
            gl.bindTexture(gl.TEXTURE_2D, tex);
          }
        };
      }

      return { create: create };
    })();
