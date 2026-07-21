/* ===== Hypervisor: Home anchor noise field (WebGL2 Bayer dither) =====
   Ports the Bayer-dithered noise field aesthetic from Hyperagent's welcome
   screen. Renders a subtle animated background behind the centered logo on
   the homepage. Torn down cleanly when navigating away. */

  (function initHomeAnchor() {
    var canvas = null;
    var gl = null;
    var prog = null;
    var vao = null;
    var raf = null;
    var t = 0;
    var host = null;

    // Rotating greetings — one is chosen at random on every home load.
    // Written in the terminal-brutalist voice: short, direct, Operator/V-flavored.
    var GREETINGS = [
      'welcome back, operator.',
      'workspace online.',
      'good to see you, V.',
      'systems nominal.',
      'hyperspace loaded.',
      'ready when you are.',
      'let\'s get to work.',
      'signal acquired.',
      'context restored.',
      'the vault, as you left it.',
      'still here. still working.',
      'no drift detected.',
      'awaiting instruction.',
      'all lines open.',
      'buffer clear. proceed.',
      'the map is up to date.',
      // Kaomoji greetings — canonical list from steering
      '[+1]',
      '(-_-)b',
      '[✓]',
      '\\o/',
      '(._.)',
      '(?_?)',
      '(￣^￣)ゞ',
      '(　-_-)旦~',
      '(._. )'
    ];

    var VERT = '#version 300 es\nvoid main(){float x=float(gl_VertexID%2)*4.0-1.0;float y=float(gl_VertexID/2)*4.0-1.0;gl_Position=vec4(x,y,0,1);}';

    var FRAG = [
      '#version 300 es',
      'precision highp float;',
      'uniform vec2 u_resolution;',
      'uniform float u_time;',
      'uniform vec3 u_tint;',
      'out vec4 fragColor;',
      '',
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
      '}',
      '',
      'void main() {',
      '    float t = u_time;',
      '    float cellSize = max(2.0, floor(min(u_resolution.x, u_resolution.y) / 200.0));',
      '    vec2 cellUv = floor(gl_FragCoord.xy / cellSize) * cellSize;',
      '    vec2 cellPos = cellUv / u_resolution;',
      '',
      '    // Moving radial center',
      '    float cx = 0.5 + sin(t * 0.4) * 0.3;',
      '    float cy = 0.5 + cos(t * 0.3) * 0.3;',
      '    vec2 d = cellPos - vec2(cx, cy);',
      '    float dist = length(d);',
      '',
      '    // Three overlapping trig waves',
      '    float g1 = 0.5 + 0.5 * sin(dist * 6.0 - t * 0.8);',
      '    float g2 = 0.5 + 0.5 * sin((cellUv.x + cellUv.y) * 0.0032 + t * 0.5);',
      '    float g3 = 0.5 + 0.5 * cos((cellUv.y - cellUv.x) * 0.0041 - t * 0.3);',
      '    float val = g1 * 0.5 + g2 * 0.25 + g3 * 0.25;',
      '',
      '    // Squared falloff for dither density',
      '    val = val * val;',
      '',
      '    // Bayer 8x8 dither — clean on/off, gradient via pixel density',
      '    float threshold = bayer8(gl_FragCoord.xy / cellSize);',
      '    if (val < threshold) { fragColor = vec4(0.0, 0.0, 0.0, 1.0); return; }',
      '',
      '    fragColor = vec4(u_tint, 1.0);',
      '}'
    ].join('\n');

    function readAccentTint() {
      // Read --accent CSS variable and convert #rrggbb → normalized rgb.
      // Used to color the dither pixels so the field shifts with palette.
      // We dim it heavily (multiplied by 0.15) so the noise reads as ambient
      // texture rather than an active graphic.
      try {
        var raw = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
        var m = /^#?([0-9a-f]{6})$/i.exec(raw);
        if (m) {
          var hex = m[1];
          var r = parseInt(hex.substr(0, 2), 16) / 255;
          var g = parseInt(hex.substr(2, 2), 16) / 255;
          var b = parseInt(hex.substr(4, 2), 16) / 255;
          return [r * 0.15, g * 0.15, b * 0.15];
        }
      } catch (e) {}
      return [0.09, 0.09, 0.09];
    }

    function initGL() {
      if (!canvas) return false;
      gl = canvas.getContext('webgl2', { alpha: false, antialias: false });
      if (!gl) return false;
      var vs = gl.createShader(gl.VERTEX_SHADER);
      gl.shaderSource(vs, VERT); gl.compileShader(vs);
      var fs = gl.createShader(gl.FRAGMENT_SHADER);
      gl.shaderSource(fs, FRAG); gl.compileShader(fs);
      if (!gl.getShaderParameter(fs, gl.COMPILE_STATUS)) {
        console.error('[home-anchor] frag compile:', gl.getShaderInfoLog(fs));
        gl = null; return false;
      }
      prog = gl.createProgram();
      gl.attachShader(prog, vs); gl.attachShader(prog, fs);
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        console.error('[home-anchor] link:', gl.getProgramInfoLog(prog));
        gl = null; prog = null; return false;
      }
      vao = gl.createVertexArray();
      return true;
    }

    function frame() {
      if (!gl || !canvas || !host) { raf = null; return; }
      var w = host.clientWidth || 1;
      var h = host.clientHeight || 1;
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      gl.viewport(0, 0, w, h);
      gl.useProgram(prog);
      gl.bindVertexArray(vao);
      gl.uniform2f(gl.getUniformLocation(prog, 'u_resolution'), w, h);
      gl.uniform1f(gl.getUniformLocation(prog, 'u_time'), t);
      var tint = readAccentTint();
      gl.uniform3f(gl.getUniformLocation(prog, 'u_tint'), tint[0], tint[1], tint[2]);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      t += 1 / 60;
      raf = requestAnimationFrame(frame);
    }

    function start(hostEl) {
      if (!hostEl) return;
      teardown(true); // idempotent
      host = hostEl;
      canvas = document.createElement('canvas');
      canvas.className = 'home-anchor-canvas';
      // Mount as first child so the SVG (z-index:1) renders on top
      host.insertBefore(canvas, host.firstChild);
      canvas.width = host.clientWidth;
      canvas.height = host.clientHeight;
      t = Math.random() * 1000;
      if (initGL()) {
        raf = requestAnimationFrame(frame);
      }
    }

    function teardown(immediate) {
      if (raf) { cancelAnimationFrame(raf); raf = null; }
      if (gl) {
        if (prog) gl.deleteProgram(prog);
        gl = null; prog = null; vao = null;
      }
      if (canvas) {
        var c = canvas;
        canvas = null;
        host = null;
        if (immediate) {
          if (c.parentNode) c.parentNode.removeChild(c);
        } else {
          c.classList.add('fade-out');
          setTimeout(function () {
            if (c.parentNode) c.parentNode.removeChild(c);
          }, 500);
        }
      } else {
        host = null;
      }
    }

    function init(fragment) {
      if (!fragment || fragment.pageType !== 'home') return;
      var el = document.querySelector('.home-anchor');
      if (el) start(el);
      // Populate a fresh random greeting on every home visit
      var g = document.querySelector('[data-home-greeting]');
      if (g) {
        var greeting = GREETINGS[Math.floor(Math.random() * GREETINGS.length)];
        g.textContent = greeting;
        // Kaomoji greetings (anything not starting with an ASCII letter) get
        // the .emote glow treatment. The compound selector
        // .home-anchor-greeting.emote in CSS handles the styling.
        var isEmote = !/^[a-zA-Z]/.test(greeting);
        g.classList.toggle('emote', isEmote);
      }
    }

    if (window.__router) {
      window.__router.onNavigate(function () { teardown(false); }, init);
    }
  })();
